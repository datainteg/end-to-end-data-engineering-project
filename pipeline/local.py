"""Offline reference: immutable JSONL attempts and transactional SQLite warehouse.

This backend demonstrates correctness without pretending to execute Glue/Snowflake.
Full snapshots deliberately simplify the local extraction boundary.
"""
import argparse
import hashlib
import json
import sqlite3
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
from .contracts import digest, identifier, stamp, validate
from .fixture import DATASETS, KEYS, BASELINE_UPPER, baseline, changed

DDL = """
CREATE TABLE IF NOT EXISTS batch_ledger(batch_id TEXT PRIMARY KEY, upper_utc TEXT NOT NULL, manifest_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watermarks(dataset TEXT PRIMARY KEY, upper_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dim_customer(customer_sk INTEGER PRIMARY KEY, customer_id TEXT NOT NULL,
 city TEXT, loyalty_tier TEXT, attr_hash TEXT NOT NULL, valid_from TEXT NOT NULL,
 valid_to TEXT, is_current INTEGER NOT NULL, is_deleted INTEGER NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_current ON dim_customer(customer_id) WHERE is_current=1;
CREATE TABLE IF NOT EXISTS dim_product(product_id TEXT PRIMARY KEY, product_name TEXT, category TEXT, is_deleted INTEGER);
CREATE TABLE IF NOT EXISTS dim_date(date_key TEXT PRIMARY KEY, year INTEGER, month INTEGER, day INTEGER);
CREATE TABLE IF NOT EXISTS fact_orders(order_id TEXT PRIMARY KEY, customer_sk INTEGER REFERENCES dim_customer,
 date_key TEXT REFERENCES dim_date, status TEXT, is_deleted INTEGER);
CREATE TABLE IF NOT EXISTS fact_sales(order_id TEXT, line_id TEXT, customer_sk INTEGER REFERENCES dim_customer,
 product_id TEXT REFERENCES dim_product, quantity INTEGER, revenue_paise INTEGER, is_deleted INTEGER,
 PRIMARY KEY(order_id,line_id), FOREIGN KEY(order_id) REFERENCES fact_orders);
CREATE TABLE IF NOT EXISTS fact_payments(payment_id TEXT PRIMARY KEY, order_id TEXT REFERENCES fact_orders,
 amount_paise INTEGER, status TEXT, is_deleted INTEGER);
CREATE TABLE IF NOT EXISTS quality(batch_id TEXT, dataset TEXT, input_count INTEGER,
 accepted INTEGER, quarantined INTEGER, duplicates INTEGER, PRIMARY KEY(batch_id,dataset));
CREATE VIEW IF NOT EXISTS mart_sales AS
 SELECT s.*, o.date_key, c.customer_id, c.loyalty_tier AS tier_observed_at_first_publication
 FROM fact_sales s JOIN fact_orders o USING(order_id) JOIN dim_customer c ON s.customer_sk=c.customer_sk
 WHERE o.status='paid' AND o.is_deleted=0 AND s.is_deleted=0;
"""


def connect(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "warehouse.sqlite", timeout=1, isolation_level=None)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(DDL)
    return db


def money(value):
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d < 0 or d != d.quantize(Decimal("0.01")) or d >= Decimal("10000000000000000"):
            raise ValueError("INVALID_MONEY")
        return int(d * 100)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("INVALID_MONEY") from exc


def extract(root, data, batch_id, upper, attempt_id=None):
    """Archive a controlled complete source snapshot. Never overwrite attempts."""
    root = Path(root)
    identifier(batch_id)
    attempt_id = identifier(attempt_id or uuid.uuid4().hex)
    stamp(upper)
    base = root / f"raw/batch_id={batch_id}/attempt_id={attempt_id}"
    base.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema_version=1, pipeline_id="ecommerce", batch_id=batch_id,
                    attempt_id=attempt_id, window_upper_utc=upper, created_at=datetime.now(timezone.utc).isoformat(), datasets=[])
    for name in DATASETS:
        rows = data[name]
        if any(stamp(r["updated_at"]) >= stamp(upper) for r in rows):
            raise ValueError("Snapshot contains records at/after upper bound; freeze sources before extraction")
        folder = base / f"dataset={name}"
        folder.mkdir()
        path = folder / "part-00000.jsonl"
        content = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
        files = []
        if rows:
            path.write_bytes(content)
            files.append(dict(key=path.relative_to(root).as_posix(), bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
        manifest["datasets"].append(dict(name=name, source="mongodb" if name == "customers" else "postgresql",
            mode="snapshot", lower_utc="1970-01-01T00:00:00Z", upper_utc=upper, status="COMPLETE",
            schema_fingerprint=digest(sorted(rows[0]) if rows else list(KEYS[name])), record_count=len(rows), files=files))
    path = base / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def read_attempt(root, manifest):
    root = Path(root).resolve()
    def metadata(key):
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError("File escaped archive root")
        content = path.read_bytes()
        return dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    validate(manifest, metadata)
    data = {}
    for d in manifest["datasets"]:
        rows = [json.loads(line) for f in d["files"] for line in (root / f["key"]).read_text().splitlines()]
        if len(rows) != d["record_count"]:
            raise ValueError("Record count mismatch")
        data[d["name"]] = rows
    return data


def clean(data):
    result, audit, rejected = {}, {}, []
    required = {
        "orders": {"customer_id", "ordered_at", "status", "currency"},
        "order_items": {"product_id", "quantity", "unit_price", "discount_amount"},
        "payments": {"order_id", "amount", "status", "attempted_at"},
        "products": {"product_name", "category"}, "customers": {"profile"}}
    for name, rows in data.items():
        latest, payloads = {}, {}
        for r in rows:
            fields = set(KEYS[name]) | required[name] | {"updated_at", "is_deleted"}
            if not fields <= r.keys() or any(r[k] is None for k in fields):
                raise ValueError(f"Required schema field missing: {name}")
            if any(not isinstance(r[k], str) or not r[k] for k in KEYS[name]) or type(r["is_deleted"]) is not bool:
                raise ValueError("Invalid key/deletion type")
            key, ts = tuple(r[k] for k in KEYS[name]), stamp(r["updated_at"])
            version = key + (ts,)
            if version in payloads and payloads[version] != digest(r):
                raise ValueError("Conflicting payloads at the same key/time")
            payloads[version] = digest(r)
            if key not in latest or ts > stamp(latest[key]["updated_at"]):
                latest[key] = r
        accepted = []
        for r in latest.values():
            try:
                if name == "order_items":
                    if type(r["quantity"]) is not int or r["quantity"] <= 0:
                        raise ValueError("NONPOSITIVE_QUANTITY")
                    if money(r["discount_amount"]) > r["quantity"] * money(r["unit_price"]):
                        raise ValueError("EXCESS_DISCOUNT")
                elif name == "payments":
                    money(r["amount"])
                    stamp(r["attempted_at"])
                    if r["status"] not in {"SUCCESS", "FAILED", "PENDING"}:
                        raise ValueError("INVALID_PAYMENT_STATUS")
                elif name == "orders":
                    stamp(r["ordered_at"])
                    if r["currency"] != "INR" or r["status"] not in {"paid", "cancelled", "pending"}:
                        raise ValueError("INVALID_ORDER_STATUS_OR_CURRENCY")
                elif name == "customers":
                    if not isinstance(r["profile"], dict) or not isinstance(r["profile"].get("loyalty_tier"), str):
                        raise ValueError("INVALID_PROFILE")
                accepted.append(r)
            except ValueError as exc:
                # Only enumerated line/payment monetary rules are quarantinable.
                if name not in {"order_items", "payments"}:
                    raise
                rejected.append(dict(dataset=name, reason=str(exc), row=r))
        result[name] = accepted
        audit[name] = dict(input=len(rows), accepted=len(accepted), quarantined=len(latest)-len(accepted), duplicates=len(rows)-len(latest))
    customers = {r["customer_id"] for r in result["customers"]}
    products = {r["product_id"] for r in result["products"]}
    orders = {r["order_id"] for r in result["orders"]}
    if any(r["customer_id"] not in customers for r in result["orders"]) or any(r["order_id"] not in orders or r["product_id"] not in products for r in result["order_items"]) or any(r["order_id"] not in orders for r in result["payments"]):
        raise ValueError("Broken reference; publication blocked")
    return result, audit, rejected


def publish(root, manifest_path, fail_at=None):
    manifest = json.loads(Path(manifest_path).read_text())
    batch, upper = manifest["batch_id"], manifest["window_upper_utc"]
    data, audit, rejected = clean(read_attempt(root, manifest))
    if any(stamp(r["updated_at"]) >= stamp(upper) for rows in data.values() for r in rows):
        raise ValueError("Record outside selected upper bound")
    payload_hash = digest(data)
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")  # Serialized writer across processes.
        ledger = db.execute("SELECT upper_utc,manifest_hash FROM batch_ledger WHERE batch_id=?", (batch,)).fetchone()
        if ledger:
            if ledger != (upper, payload_hash):
                raise ValueError("Batch ID already committed with different content/bounds")
            db.rollback()
            return {"status": "ALREADY_PUBLISHED", "batch_id": batch}
        prior = db.execute("SELECT MAX(upper_utc) FROM watermarks").fetchone()[0]
        if prior and stamp(upper) <= stamp(prior):
            raise ValueError("Publication upper bound must advance")
        for r in data["customers"]:
            city, tier = r["profile"].get("city"), r["profile"]["loyalty_tier"]
            h = digest([city, tier, r["is_deleted"]])
            old = db.execute("SELECT customer_sk,attr_hash FROM dim_customer WHERE customer_id=? AND is_current=1", (r["customer_id"],)).fetchone()
            if old and old[1] == h:
                continue
            if old:
                db.execute("UPDATE dim_customer SET valid_to=?,is_current=0 WHERE customer_sk=?", (upper, old[0]))
            db.execute("INSERT INTO dim_customer(customer_id,city,loyalty_tier,attr_hash,valid_from,is_current,is_deleted) VALUES(?,?,?,?,?,1,?)", (r["customer_id"],city,tier,h,upper,r["is_deleted"]))
        if fail_at == "after_dimensions":
            raise RuntimeError("Injected publication failure")
        for r in data["products"]:
            db.execute("INSERT INTO dim_product VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET product_name=excluded.product_name,category=excluded.category,is_deleted=excluded.is_deleted", (r["product_id"],r["product_name"],r["category"],r["is_deleted"]))
        for r in data["orders"]:
            dt = stamp(r["ordered_at"])
            dk = dt.date().isoformat()
            db.execute("INSERT OR IGNORE INTO dim_date VALUES(?,?,?,?)", (dk,dt.year,dt.month,dt.day))
            sk = db.execute("SELECT customer_sk FROM dim_customer WHERE customer_id=? AND is_current=1", (r["customer_id"],)).fetchone()[0]
            old = db.execute("SELECT c.customer_id FROM fact_orders o JOIN dim_customer c USING(customer_sk) WHERE order_id=?", (r["order_id"],)).fetchone()
            if old and old[0] != r["customer_id"]:
                raise ValueError("Changing order ownership requires explicit restatement")
            db.execute("INSERT INTO fact_orders VALUES(?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET date_key=excluded.date_key,status=excluded.status,is_deleted=excluded.is_deleted", (r["order_id"],sk,dk,r["status"],r["is_deleted"]))
        for r in data["order_items"]:
            sk = db.execute("SELECT customer_sk FROM fact_orders WHERE order_id=?", (r["order_id"],)).fetchone()[0]
            revenue = r["quantity"] * money(r["unit_price"]) - money(r["discount_amount"])
            db.execute("INSERT INTO fact_sales VALUES(?,?,?,?,?,?,?) ON CONFLICT(order_id,line_id) DO UPDATE SET product_id=excluded.product_id,quantity=excluded.quantity,revenue_paise=excluded.revenue_paise,is_deleted=excluded.is_deleted", (r["order_id"],r["line_id"],sk,r["product_id"],r["quantity"],revenue,r["is_deleted"]))
        for r in data["payments"]:
            db.execute("INSERT INTO fact_payments VALUES(?,?,?,?,?) ON CONFLICT(payment_id) DO UPDATE SET order_id=excluded.order_id,amount_paise=excluded.amount_paise,status=excluded.status,is_deleted=excluded.is_deleted", (r["payment_id"],r["order_id"],money(r["amount"]),r["status"],r["is_deleted"]))
        # Reject invalid corrections to existing facts instead of silently retaining stale values.
        for r in rejected:
            row = r["row"]
            if r["dataset"] == "order_items":
                exists = db.execute("SELECT 1 FROM fact_sales WHERE order_id=? AND line_id=?", (row["order_id"],row["line_id"])).fetchone()
            else:
                exists = db.execute("SELECT 1 FROM fact_payments WHERE payment_id=?", (row["payment_id"],)).fetchone()
            if exists:
                raise ValueError("Invalid correction to published fact; publication blocked")
        for name, counts in audit.items():
            db.execute("INSERT INTO quality VALUES(?,?,?,?,?,?)", (batch,name,counts["input"],counts["accepted"],counts["quarantined"],counts["duplicates"]))
            db.execute("INSERT INTO watermarks VALUES(?,?) ON CONFLICT(dataset) DO UPDATE SET upper_utc=excluded.upper_utc", (name,upper))
        db.execute("INSERT INTO batch_ledger VALUES(?,?,?)", (batch,upper,payload_hash))
        # Persist evidence before COMMIT; the ledger remains authoritative if a later I/O fails.
        out = Path(root) / "audit" / batch
        out.mkdir(parents=True, exist_ok=True)
        (out / "quality.json").write_text(json.dumps(audit, indent=2) + "\n")
        (out / "rejected.json").write_text(json.dumps(rejected, indent=2) + "\n")
        if fail_at == "before_commit":
            raise RuntimeError("Injected failure before commit")
        db.commit()
        return {"status": "PUBLISHED", "batch_id": batch, "quarantined": len(rejected)}
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def metrics(root):
    db = connect(root)
    try:
        sales = db.execute("SELECT COALESCE(SUM(revenue_paise),0) FROM mart_sales").fetchone()[0]
        orders = db.execute("SELECT COUNT(*) FROM fact_orders WHERE status='paid' AND is_deleted=0").fetchone()[0]
        success, attempts = db.execute("SELECT COALESCE(SUM(status='SUCCESS'),0),COUNT(*) FROM fact_payments WHERE is_deleted=0").fetchone()
        return dict(net_sales=f"{Decimal(sales)/100:.2f}", paid_orders=orders,
                    aov=f"{Decimal(sales)/100/orders:.2f}" if orders else "0.00",
                    payment_success_rate=f"{Decimal(success)/attempts:.4f}" if attempts else "0.0000")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "metrics", "publish", "customer-change"])
    parser.add_argument("--root", default=".runtime")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    if args.command == "demo":
        m = extract(args.root, baseline(), "baseline", BASELINE_UPPER)
        print(json.dumps(publish(args.root, m)))
        print(json.dumps(publish(args.root, m)))
    elif args.command == "customer-change":
        m = extract(args.root, changed(baseline()), "customer-change", "2026-01-03T00:00:00Z")
        print(json.dumps(publish(args.root, m)))
    elif args.command == "publish":
        if not args.manifest:
            parser.error("--manifest is required")
        print(json.dumps(publish(args.root, args.manifest)))
    print(json.dumps(metrics(args.root), indent=2))


if __name__ == "__main__":
    main()
