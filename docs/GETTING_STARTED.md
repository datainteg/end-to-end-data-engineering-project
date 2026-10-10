# Local step-by-step guide

Run commands from the repository root. The verified offline route uses Python's standard library only. Docker and optional database clients are needed only for the second route.

## 1. Check your environment

```bash
python3 --version
python3 -m unittest discover -s tests -v
```

Use Python 3.11 or newer. Windows users can replace `python3` with `py -3`; Bash examples require WSL/Git Bash. No virtual environment is required for the offline route.

## 2. Publish and replay the baseline

```bash
python3 -m pipeline.local demo
```

Expect `PUBLISHED` followed by `ALREADY_PUBLISHED`, with net sales 1200.00, paid orders 2, AOV 600.00 and payment-success rate 0.5000. Subsequent runs report `ALREADY_PUBLISHED` twice. Files are created under `.runtime/raw/`, quality records under `.runtime/audit/`, and the warehouse at `.runtime/warehouse.sqlite`.

The fixture contains three orders, three lines, four payment attempts, three products and two customers. The cancelled order contributes no sales. Payment attempts are a separate fact table, so a failed attempt followed by success does not duplicate the order line.

## 3. Inspect the warehouse

```bash
python3 - <<'PY'
from pipeline.local import connect
with connect('.runtime') as db:
    for table in ['fact_orders','fact_sales','fact_payments','dim_customer','watermarks','batch_ledger']:
        print(table, db.execute(f'SELECT * FROM {table}').fetchall())
PY
```

Revenue is stored in integer **paise** in the local warehouse. ₹900 appears as 90000; divide by 100 for rupees. This avoids binary floating-point rounding. `mart_sales` filters paid, nondeleted orders and lines. Product/customer soft deletion marks dimensions but does not erase earlier sales.

## 4. Demonstrate customer history

```bash
python3 -m pipeline.local customer-change
```

Inspect `dim_customer` again: C001 has a closed Silver row and one current Gold row. C002 is unchanged. Facts keep the surrogate key assigned at first publication. These are observed batch versions, not a reconstruction of every source change or the customer's exact tier at order time.

## 5. Demonstrate failed validation and recovery

Use a separate scratch warehouse so the normal demo remains available:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from pipeline.fixture import baseline, BASELINE_UPPER
from pipeline.local import extract, publish, connect
root = Path('.runtime/failure-demo')
m = extract(root, baseline(), 'missing-file', BASELINE_UPPER)
manifest = json.loads(m.read_text())
p = root / manifest['datasets'][0]['files'][0]['key']
original = p.read_bytes()
p.unlink()
try:
    publish(root, m)
except FileNotFoundError:
    print('EXPECTED: missing object blocked publication')
with connect(root) as db:
    print('Committed batches:', db.execute('SELECT COUNT(*) FROM batch_ledger').fetchone()[0])
p.write_bytes(original)  # Local demonstration only: restore the exact original bytes.
print(publish(root, m))
PY
```

On a fresh scratch root, the ledger remains empty until recovery. For real immutable cloud attempts, preserve evidence and use the documented recovery boundary; do not modify published objects. The automated suite additionally injects transaction failures and checks unchanged dimensions and watermarks.

## 6. Optional real source containers

```bash
cp .env.example .env
# Edit .env and replace both passwords before continuing.
docker compose --env-file .env -f local/docker-compose.yml up -d --wait
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-sources.lock.txt
set -a
. ./.env
set +a
python -m scripts.seed_sources --reset-demo
python -m scripts.check_sources
```

If a port is already occupied, set `PGPORT` or `MONGO_PORT` in `.env` before starting; the seed tool uses the same values. These credentials are for local containers only. Ports bind to loopback. The MongoDB `demo` user is a container bootstrap administrator; create a read-only source user for cloud work. Compose does not configure TLS and must not be exposed as-is to a public network. The fixture seed updates only known fixture keys and keeps other records intact.

The seed script writes PostgreSQL amounts as NUMERIC and MongoDB `updated_at` as BSON datetime. Inspect sources with `docker compose --env-file .env -f local/docker-compose.yml exec postgres psql -U demo -d ecommerce` and a MongoDB client. Do not show credentials in recordings.

`python -m scripts.seed_sources --reset-demo --customer-change` applies the deterministic customer change. Run the next cloud batch with an upper bound later than its source timestamps. Freeze source edits during the small snapshot demonstration.

Local containers do **not** automatically make databases reachable from Glue. Continue with [cloud setup](CLOUD_SETUP.md) for private routing and connection tests.

## 7. Stop and clean up

```bash
docker compose --env-file .env -f local/docker-compose.yml stop
```

Stopping retains volumes. To remove only this project's containers, run `down` with the same flags. Add `--volumes` only when you intend to delete the demo databases. Local `.runtime/` is disposable after you retain any evidence you need. Use another `--root` for experiments instead of deleting a warehouse you still need.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No module named pipeline` | Run from the cloned repository root |
| Batch already exists with different content | Use a new batch ID; replay requires the original selected data |
| Upper bound must advance | Use a later UTC upper bound and a new batch ID |
| `database is locked` | Another publisher holds the local transaction; wait for it to finish |
| File checksum mismatch | Restore exact raw evidence or extract a new attempt |
| Container auth fails after changing `.env` | Existing volumes retain old database passwords; changing env does not rotate them |
| Source timestamp is outside upper bound | Freeze sources and choose a later bound; do not silently discard new records |
