import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from pipeline.fixture import baseline, changed, BASELINE_UPPER
from pipeline.local import extract, publish, metrics, connect, clean


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = baseline()
        self.manifest = extract(self.root, self.data, "baseline", BASELINE_UPPER)

    def sql(self, query):
        db = connect(self.root)
        try:
            return db.execute(query).fetchall()
        finally:
            db.close()

    def test_baseline_replay_and_customer_history(self):
        publish(self.root, self.manifest)
        expected = dict(net_sales="1200.00", paid_orders=2, aov="600.00", payment_success_rate="0.5000")
        self.assertEqual(metrics(self.root), expected)
        self.assertEqual(publish(self.root, self.manifest)["status"], "ALREADY_PUBLISHED")
        original = self.sql("SELECT customer_sk FROM fact_sales ORDER BY order_id")
        m = extract(self.root, changed(self.data), "next", "2026-01-03T00:00:00Z")
        publish(self.root, m)
        self.assertEqual(metrics(self.root), expected)
        self.assertEqual(self.sql("SELECT customer_sk FROM fact_sales ORDER BY order_id"), original)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dim_customer"), [(3,)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dim_customer WHERE is_current=1"), [(2,)])
        self.assertEqual(self.sql("SELECT valid_to FROM dim_customer WHERE is_current=0"), [("2026-01-03T00:00:00Z",)])

    def test_rollback_preserves_targets_and_watermarks(self):
        publish(self.root, self.manifest)
        before = self.sql("SELECT * FROM watermarks")
        m = extract(self.root, changed(self.data), "next", "2026-01-03T00:00:00Z")
        for boundary in ["after_dimensions", "before_commit"]:
            with self.assertRaises(RuntimeError):
                publish(self.root, m, fail_at=boundary)
            self.assertEqual(self.sql("SELECT * FROM watermarks"), before)
            self.assertEqual(self.sql("SELECT COUNT(*) FROM dim_customer"), [(2,)])
        publish(self.root, m)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM batch_ledger"), [(2,)])

    def test_missing_or_corrupted_file_blocks_publication(self):
        m = json.loads(self.manifest.read_text())
        p = self.root / m["datasets"][0]["files"][0]["key"]
        p.write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "checksum"):
            publish(self.root, self.manifest)
        p.unlink()
        with self.assertRaises(FileNotFoundError):
            publish(self.root, self.manifest)
        self.assertEqual(self.sql("SELECT * FROM watermarks"), [])

    def test_completed_empty_snapshot_advances_watermarks(self):
        empty = {k: [] for k in self.data}
        m = extract(self.root, empty, "empty", BASELINE_UPPER)
        publish(self.root, m)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM watermarks"), [(5,)])
        self.assertEqual(metrics(self.root)["net_sales"], "0.00")

    def test_quality_accounting_and_duplicate_conflict(self):
        bad = deepcopy(self.data["order_items"][0])
        bad.update(line_id="bad", quantity=-1)
        self.data["order_items"].extend([bad, deepcopy(self.data["order_items"][0])])
        good, audit, rejected = clean(self.data)
        self.assertEqual(rejected[0]["reason"], "NONPOSITIVE_QUANTITY")
        self.assertEqual(audit["order_items"], dict(input=5, accepted=3, quarantined=1, duplicates=1))
        self.data["order_items"][-1]["quantity"] = 9
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            clean(self.data)

    def test_soft_delete_and_unchanged_lookup(self):
        publish(self.root, self.manifest)
        self.data["order_items"][0].update(is_deleted=True, updated_at="2026-01-02T12:00:00Z")
        m = extract(self.root, self.data, "delete", "2026-01-03T00:00:00Z")
        publish(self.root, m)
        self.assertEqual(metrics(self.root)["net_sales"], "300.00")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM dim_customer"), [(2,)])

    def test_reused_batch_with_different_content_fails(self):
        publish(self.root, self.manifest)
        m = extract(self.root, changed(self.data), "baseline", "2026-01-03T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "different content"):
            publish(self.root, m)

    def test_late_older_batch_cannot_rewind_watermark(self):
        publish(self.root, self.manifest)
        m = extract(self.root, self.data, "old", "2026-01-01T12:00:00Z")
        with self.assertRaisesRegex(ValueError, "advance"):
            publish(self.root, m)

    def test_broken_reference_and_missing_schema_fail(self):
        self.data["orders"][0]["customer_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "Broken reference"):
            clean(self.data)
        del self.data["orders"][0]["currency"]
        with self.assertRaisesRegex(ValueError, "schema"):
            clean(self.data)

    def test_invalid_correction_does_not_hide_stale_fact(self):
        publish(self.root, self.manifest)
        self.data["order_items"][0].update(quantity=-1, updated_at="2026-01-02T12:00:00Z")
        m = extract(self.root, self.data, "bad-correction", "2026-01-03T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "Invalid correction"):
            publish(self.root, m)
        self.assertEqual(metrics(self.root)["net_sales"], "1200.00")

    def test_path_escape_and_manifest_missing_source(self):
        m = json.loads(self.manifest.read_text())
        m["datasets"][0]["files"][0]["key"] = "../../etc/passwd"
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "file reference"):
            publish(self.root, self.manifest)
        m["datasets"].pop()
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "dataset"):
            publish(self.root, self.manifest)

    def test_writer_lock_prevents_concurrent_publication(self):
        db = connect(self.root)
        db.execute("BEGIN IMMEDIATE")
        try:
            import sqlite3
            with self.assertRaises(sqlite3.OperationalError):
                publish(self.root, self.manifest)
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()
