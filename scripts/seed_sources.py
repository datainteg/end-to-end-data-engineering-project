"""Seed only the synthetic fixture IDs. Run as python -m scripts.seed_sources.

Explicit --reset-demo resets fixture rows; it does not truncate unrelated rows.
"""
import argparse
import os
from datetime import datetime
from pathlib import Path
from pipeline.fixture import baseline, changed


def main():
    import psycopg
    from psycopg import sql
    from pymongo import MongoClient
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-demo", action="store_true", required=True)
    parser.add_argument("--customer-change", action="store_true")
    args = parser.parse_args()
    data = changed(baseline()) if args.customer_change else baseline()
    with psycopg.connect(host=os.environ.get("PGHOST", "127.0.0.1"), port=os.environ.get("PGPORT", "5432"),
                         dbname=os.environ.get("PGDATABASE", "ecommerce"), user=os.environ.get("PGUSER", "demo"),
                         password=os.environ["POSTGRES_PASSWORD"]) as conn:
        conn.execute((Path(__file__).resolve().parents[1] / "sources/postgresql/schema.sql").read_text())
        for name in ["products", "orders", "order_items", "payments"]:
            for row in data[name]:
                fields = list(row)
                key = ["order_id", "line_id"] if name == "order_items" else [{"products":"product_id", "orders":"order_id", "payments":"payment_id"}[name]]
                query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}").format(
                    sql.Identifier(name), sql.SQL(",").join(map(sql.Identifier, fields)),
                    sql.SQL(",").join(sql.Placeholder() for _ in fields), sql.SQL(",").join(map(sql.Identifier,key)),
                    sql.SQL(",").join(sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(k),sql.Identifier(k)) for k in fields if k not in key))
                conn.execute(query, [row[k] for k in fields])
    with MongoClient(host=os.environ.get("MONGO_HOST", "127.0.0.1"), port=int(os.environ.get("MONGO_PORT", "27017")),
                     username=os.environ.get("MONGO_USER", "demo"), password=os.environ["MONGO_PASSWORD"], authSource="admin", serverSelectionTimeoutMS=10000) as client:
        collection = client.ecommerce.customers
        collection.create_index("customer_id", unique=True)
        collection.create_index("updated_at")
        for row in data["customers"]:
            row["updated_at"] = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
            collection.replace_one({"customer_id": row["customer_id"]}, row, upsert=True)
    print("Seeded synthetic fixture IDs into PostgreSQL and MongoDB.")


if __name__ == "__main__":
    main()
