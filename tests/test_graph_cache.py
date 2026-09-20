"""
Unit tests for Thread-Safe LRU Query Cache (src/graph/cache.py)
"""

import sys
import time
import threading
import unittest
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.graph.cache import LRUQueryCache
from src.graph.client import GraphClient


class TestGraphCache(unittest.TestCase):
    def setUp(self):
        self.cache = LRUQueryCache(max_capacity=5, ttl_seconds=2.0)

    def test_basic_get_put(self):
        self.cache.put("k1", {"val": 100}, tags={"tagA"})
        res = self.cache.get("k1")
        self.assertIsNotNone(res)
        self.assertEqual(res["val"], 100)
        self.assertEqual(self.cache.hits, 1)

        # Non-existent key
        self.assertIsNone(self.cache.get("k_missing"))
        self.assertEqual(self.cache.misses, 1)

    def test_lru_eviction(self):
        # Insert 5 entries (max capacity)
        for i in range(1, 6):
            self.cache.put(f"k{i}", i)

        self.assertEqual(self.cache.stats()["current_size"], 5)

        # Access k1 to make it most recently used
        self.assertEqual(self.cache.get("k1"), 1)

        # Insert k6 -> should evict k2 (oldest unaccessed)
        self.cache.put("k6", 6)
        self.assertEqual(self.cache.evictions, 1)
        self.assertIsNone(self.cache.get("k2"))
        self.assertIsNotNone(self.cache.get("k1"))
        self.assertIsNotNone(self.cache.get("k6"))

    def test_ttl_expiration(self):
        short_cache = LRUQueryCache(max_capacity=10, ttl_seconds=0.1)
        short_cache.put("k_temp", "valid")
        self.assertEqual(short_cache.get("k_temp"), "valid")

        # Sleep past TTL
        time.sleep(0.15)
        self.assertIsNone(short_cache.get("k_temp"))

    def test_tag_invalidation(self):
        self.cache.put("card_C101_q1", {"profile": 1}, tags={"C101", "CUST_1"})
        self.cache.put("card_C101_q3", {"velocity": 5}, tags={"C101"})
        self.cache.put("card_C102_q1", {"profile": 2}, tags={"C102"})

        # Invalidate C101
        count = self.cache.invalidate_by_tag("C101")
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get("card_C101_q1"))
        self.assertIsNone(self.cache.get("card_C101_q3"))
        self.assertIsNotNone(self.cache.get("card_C102_q1"))

    def test_thread_safety(self):
        concurrent_cache = LRUQueryCache(max_capacity=100, ttl_seconds=10.0)

        def worker(worker_id: int):
            for i in range(50):
                k = f"key_{worker_id}_{i % 10}"
                concurrent_cache.put(k, i, tags={f"tag_{worker_id}"})
                concurrent_cache.get(k)
                if i % 15 == 0:
                    concurrent_cache.invalidate_by_tag(f"tag_{worker_id}")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = concurrent_cache.stats()
        self.assertGreater(stats["total_requests"], 0)
        self.assertGreater(stats["hits"], 0)

    def test_graph_client_integration(self):
        custom_cache = LRUQueryCache(max_capacity=100, ttl_seconds=30.0)
        client = GraphClient(cache=custom_cache)

        # First call: cache miss, compute
        res1 = client.entity_profile("C12382-K1", entity_type="card", as_of="2016-12-05 01:55:28")
        self.assertEqual(custom_cache.hits, 0)
        self.assertEqual(custom_cache.misses, 1)

        # Second call: cache hit!
        res2 = client.entity_profile("C12382-K1", entity_type="card", as_of="2016-12-05 01:55:28")
        self.assertEqual(custom_cache.hits, 1)
        self.assertEqual(res1["txn_count"], res2["txn_count"])

        # Dynamic invalidation
        inv_count = client.invalidate_entity_cache("C12382-K1")
        self.assertGreaterEqual(inv_count, 1)

        # Third call: recomputed after invalidation
        res3 = client.entity_profile("C12382-K1", entity_type="card", as_of="2016-12-05 01:55:28")
        self.assertEqual(custom_cache.misses, 2)
        self.assertEqual(res3["txn_count"], res1["txn_count"])


if __name__ == "__main__":
    unittest.main()
