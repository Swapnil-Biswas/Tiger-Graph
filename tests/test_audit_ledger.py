"""
Unit tests for Cryptographic Tamper-Evident Audit Ledger (src/policy/audit_ledger.py)
"""

import sys
import json
import shutil
import threading
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.policy.audit_ledger import CryptographicAuditLedger, GENESIS_PREV_HASH


class TestAuditLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = CryptographicAuditLedger(secret_key=b"test-secret-key-12345")
        self.scratch_dir = ROOT_DIR / "scratch" / "test_ledger"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir)

    def test_genesis_and_chain_append(self):
        e0 = self.ledger.append("HHG-001", "FraudInvestigatorAgent", "CREATE_CASE", {"exposure": 77.07})
        self.assertEqual(e0.index, 0)
        self.assertEqual(e0.prev_hash, GENESIS_PREV_HASH)
        self.assertEqual(len(e0.entry_hash), 64)
        self.assertEqual(len(e0.signature), 64)

        e1 = self.ledger.append("HHG-001", "AMLSpecialistAgent", "BLOCK_CARD", {"card_id": "C12382-K1"})
        self.assertEqual(e1.index, 1)
        self.assertEqual(e1.prev_hash, e0.entry_hash)

        ok, msg = self.ledger.verify_chain()
        self.assertTrue(ok)
        self.assertIn("100% intact", msg)

    def test_tamper_detection_payload(self):
        self.ledger.append("HHG-001", "Agent", "CREATE_CASE", {"exposure": 100.0})
        self.ledger.append("HHG-002", "Agent", "BLOCK_CARD", {"card_id": "C2"})

        # Tamper with entry 0 payload
        self.ledger._entries[0].payload["exposure"] = 9999.99

        ok, msg = self.ledger.verify_chain()
        self.assertFalse(ok)
        self.assertIn("Tampered content at index 0", msg)

    def test_tamper_detection_signature(self):
        self.ledger.append("HHG-001", "Agent", "CREATE_CASE", {"exposure": 100.0})

        # Corrupt signature
        self.ledger._entries[0].signature = "0" * 64

        ok, msg = self.ledger.verify_chain()
        self.assertFalse(ok)
        self.assertIn("Invalid signature at index 0", msg)

    def test_tamper_detection_broken_chain(self):
        self.ledger.append("HHG-001", "Agent", "CREATE_CASE", {})
        self.ledger.append("HHG-002", "Agent", "BLOCK_CARD", {})

        # Break hash chain on entry 1
        self.ledger._entries[1].prev_hash = "f" * 64

        ok, msg = self.ledger.verify_chain()
        self.assertFalse(ok)
        self.assertIn("Broken hash chain at index 1", msg)

    def test_export_import_roundtrip(self):
        self.ledger.append("HHG-001", "Agent", "STEP_UP_AUTH", {"card_id": "C1"})
        self.ledger.append("HHG-001", "Supervisor", "L2_APPROVAL", {"approved": True})

        export_path = self.scratch_dir / "audit_chain.json"
        self.ledger.export_json(export_path)
        self.assertTrue(export_path.is_file())

        new_ledger = CryptographicAuditLedger(secret_key=b"test-secret-key-12345")
        ok, msg = new_ledger.import_json(export_path)
        self.assertTrue(ok)
        self.assertIn("2 audit entries cryptographically verified", msg)

    def test_concurrent_appends(self):
        concurrent_ledger = CryptographicAuditLedger()

        def worker(worker_id: int):
            for i in range(20):
                concurrent_ledger.append(f"HHG-{worker_id:03d}", f"Worker_{worker_id}", "LOG_ACTION", {"step": i})

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(concurrent_ledger._entries), 100)
        ok, msg = concurrent_ledger.verify_chain()
        self.assertTrue(ok)
        self.assertIn("100 audit entries cryptographically verified", msg)


if __name__ == "__main__":
    unittest.main()
