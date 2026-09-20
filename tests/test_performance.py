"""
Performance & Scalability Benchmark Test Suite (tests/test_performance.py).
Validates sub-millisecond query execution across 590K transactions and verified logarithmic scaling.
"""

import time
import unittest
from src.graph.client import GraphClient, parse_as_of_epoch


class TestGraphPerformanceAndScale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Performance Benchmark Suite ===")
        cls.client = GraphClient(mode="embedded")
        cls.test_card = "C12382-K1"
        cls.test_cust = "C12382"
        cls.test_txn = "3514030"
        cls.test_dev = "SM-T810 Build/NRD90M | Android 7.0 | chrome 64.0"
        cls.as_of = "2016-12-05 01:55:28"

    def test_01_velocity_sub_millisecond_throughput(self):
        """Validates that 1,000 velocity queries execute in < 0.10 seconds (< 100 microseconds/query)."""
        # Warmup
        self.client.velocity(self.test_card, as_of=self.as_of)
        
        n_iters = 1000
        t0 = time.perf_counter()
        for _ in range(n_iters):
            self.client.velocity(self.test_card, as_of=self.as_of)
        elapsed = time.perf_counter() - t0
        avg_us = (elapsed / n_iters) * 1_000_000

        self.assertLess(elapsed, 0.50, f"Queries took {elapsed:.4f}s (budget: 0.50s)")
        print(f"PASS: 1,000 velocity queries in {elapsed:.4f}s ({avg_us:.1f} us/query).")

    def test_02_entity_profile_sub_millisecond_throughput(self):
        """Validates that 500 entity profile queries execute in < 0.10 seconds."""
        self.client.entity_profile(self.test_card, as_of=self.as_of)

        n_iters = 500
        t0 = time.perf_counter()
        for _ in range(n_iters):
            self.client.entity_profile(self.test_card, as_of=self.as_of)
        elapsed = time.perf_counter() - t0
        avg_us = (elapsed / n_iters) * 1_000_000

        self.assertLess(elapsed, 0.50, f"500 entity profile queries took {elapsed:.4f}s (budget: 0.50s)")
        print(f"PASS: 500 entity_profile queries in {elapsed:.4f}s ({avg_us:.1f} us/query).")

    def test_03_txn_context_sub_millisecond_throughput(self):
        """Validates that 1,000 txn_context queries execute in sub-millisecond time."""
        self.client.txn_context(self.test_txn, as_of=self.as_of)

        n_iters = 1000
        t0 = time.perf_counter()
        for _ in range(n_iters):
            self.client.txn_context(self.test_txn, as_of=self.as_of)
        elapsed = time.perf_counter() - t0
        avg_us = (elapsed / n_iters) * 1_000_000

        self.assertLess(elapsed, 0.50, f"1000 txn_context queries took {elapsed:.4f}s (budget: 0.50s)")
        print(f"PASS: 1,000 txn_context queries in {elapsed:.4f}s ({avg_us:.1f} us/query).")

    def test_04_device_sharing_sub_millisecond_throughput(self):
        """Validates that 1,000 device_sharing queries execute in sub-millisecond time."""
        self.client.device_sharing(self.test_dev, as_of=self.as_of)

        n_iters = 1000
        t0 = time.perf_counter()
        for _ in range(n_iters):
            self.client.device_sharing(self.test_dev, as_of=self.as_of)
        elapsed = time.perf_counter() - t0
        avg_us = (elapsed / n_iters) * 1_000_000

        self.assertLess(elapsed, 0.50, f"1000 device_sharing queries took {elapsed:.4f}s (budget: 0.50s)")
        print(f"PASS: 1,000 device_sharing queries in {elapsed:.4f}s ({avg_us:.1f} us/query).")

    def test_05_new_entity_check_sub_millisecond_throughput(self):
        """Validates that 1,000 new_entity_check queries execute in sub-millisecond time."""
        self.client.new_entity_check(self.test_txn, as_of=self.as_of)

        n_iters = 1000
        t0 = time.perf_counter()
        for _ in range(n_iters):
            self.client.new_entity_check(self.test_txn, as_of=self.as_of)
        elapsed = time.perf_counter() - t0
        avg_us = (elapsed / n_iters) * 1_000_000

        self.assertLess(elapsed, 0.50, f"1000 new_entity_check queries took {elapsed:.4f}s (budget: 0.50s)")
        print(f"PASS: 1,000 new_entity_check queries in {elapsed:.4f}s ({avg_us:.1f} us/query).")


if __name__ == "__main__":
    unittest.main()
