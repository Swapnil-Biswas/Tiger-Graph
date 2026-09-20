import unittest
from fastapi.testclient import TestClient
from src.graph.client import GraphClient
from src.graph.entity_resolution import (
    jaro_similarity,
    jaro_winkler_similarity,
    parse_device_profile_key,
    ProbabilisticEntityResolver,
)
from src.api.main import app, agent


class TestProbabilisticEntityResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = agent.client
        cls.resolver = ProbabilisticEntityResolver(cls.client)
        cls.api_client = TestClient(app)

    def test_jaro_winkler_similarity(self):
        """Jaro-Winkler string similarity should score identical strings 1.0, typos high, and distinct low."""
        # Exact match
        self.assertEqual(jaro_winkler_similarity("SM-T810", "SM-T810"), 1.0)
        self.assertEqual(jaro_winkler_similarity("", ""), 1.0)

        # Minor browser point release bump
        sim_browser = jaro_winkler_similarity("chrome 65.0.3325.109", "chrome 66.0.3359.126")
        self.assertGreater(sim_browser, 0.85)

        # Email handle prefix variation
        sim_email = jaro_winkler_similarity("johnsmith1984", "john.smith1984")
        self.assertGreater(sim_email, 0.90)

        # Completely distinct strings
        sim_distinct = jaro_winkler_similarity("iOS Device", "Windows Desktop")
        self.assertLess(sim_distinct, 0.60)

    def test_fellegi_sunter_identical_profiles(self):
        """Identical profiles must yield P >= 0.999, CONFIRMED_MATCH, and RESOLVED_IDENTITY_LINK."""
        prof_a = {
            "device_model": "SM-T810 Build/NRD90M",
            "os_platform": "Android 7.0",
            "browser": "chrome 65.0.3325.109",
            "screen_res": "2048x1536",
            "email_prefix": "sarah_connor",
            "email_domain": "gmail.com",
        }
        prof_b = dict(prof_a)

        res = self.resolver.compare_profiles(prof_a, prof_b)
        self.assertGreaterEqual(res["match_probability"], 0.999)
        self.assertEqual(res["verdict"], "CONFIRMED_MATCH")
        self.assertEqual(res["link_type"], "RESOLVED_IDENTITY_LINK")
        self.assertEqual(res["recommended_action"], "MERGE_ENTITY_CLUSTER")
        self.assertGreater(res["composite_weight"], 10.0)

    def test_fellegi_sunter_fuzzy_browser_update(self):
        """Near-duplicate device profiles with minor browser version bump should resolve to CONFIRMED_MATCH."""
        prof_a = {
            "device_model": "SM-T810 Build/NRD90M",
            "os_platform": "Android 7.0",
            "browser": "chrome 65.0.3325.109",
            "screen_res": "2048x1536",
        }
        prof_b = {
            "device_model": "SM-T810 Build/NRD90M",
            "os_platform": "Android 7.0",
            "browser": "chrome 66.0.3359.126",
            "screen_res": "2048x1536",
        }

        res = self.resolver.compare_profiles(prof_a, prof_b)
        self.assertGreaterEqual(res["match_probability"], 0.95)
        self.assertEqual(res["verdict"], "CONFIRMED_MATCH")
        self.assertEqual(res["link_type"], "RESOLVED_IDENTITY_LINK")

    def test_fellegi_sunter_probable_sybil(self):
        """Matching device hardware (model + screen) but disparate OS/browser points to PROBABLE_SYBIL."""
        prof_a = {
            "device_model": "SM-T810 Build/NRD90M",
            "screen_res": "2048x1536",
            "os_platform": "Windows 10",
            "browser": "chrome 65.0.3325.109",
        }
        prof_b = {
            "device_model": "SM-T810 Build/NRD90M",
            "screen_res": "2048x1536",
            "os_platform": "Linux",
            "browser": "opera 45.0.2246.123",
        }

        res = self.resolver.compare_profiles(prof_a, prof_b)
        self.assertGreaterEqual(res["match_probability"], 0.65)
        self.assertLess(res["match_probability"], 0.85)
        self.assertEqual(res["verdict"], "PROBABLE_SYBIL")
        self.assertEqual(res["link_type"], "SUSPECTED_SYBIL_LINK")
        self.assertEqual(res["recommended_action"], "STEP_UP_AUTH_AND_EDD")

    def test_fellegi_sunter_distinct_profiles(self):
        """Completely different profiles must yield P < 0.10, DISTINCT, and NONE."""
        prof_a = {
            "device_model": "iPhone",
            "os_platform": "iOS 11.2",
            "browser": "mobile safari 11.0",
            "screen_res": "1334x750",
            "email_domain": "icloud.com",
        }
        prof_b = {
            "device_model": "Windows Desktop",
            "os_platform": "Windows 10",
            "browser": "edge 16.16299",
            "screen_res": "1920x1080",
            "email_domain": "hotmail.com",
        }

        res = self.resolver.compare_profiles(prof_a, prof_b)
        self.assertLess(res["match_probability"], 0.10)
        self.assertEqual(res["verdict"], "DISTINCT")
        self.assertEqual(res["link_type"], "NONE")
        self.assertEqual(res["recommended_action"], "MAINTAIN_SEPARATION")

    def test_resolve_device_nexus_and_sybil_discovery_api(self):
        """Candidate blocking, sybil account discovery across linked devices, and REST API validation."""
        dev_1 = "SM-T810 Build/NRD90M | Android 7.0 | chrome 65.0.3325.109 | 2048x1536"
        dev_2 = "SM-T810 Build/NRD90M | Android 7.0 | chrome 66.0.3359.126 | 2048x1536"

        card_primary = "card_sybil_primary_001"
        card_synthetic = "card_sybil_synthetic_002"

        # Register devices in store
        self.client.store.device_profiles[dev_1] = parse_device_profile_key(dev_1)
        self.client.store.device_profiles[dev_2] = parse_device_profile_key(dev_2)

        # Link cards to respective devices
        self.client.store.devices_by_card[card_primary].add(dev_1)
        self.client.store.devices_by_card[card_synthetic].add(dev_2)
        self.client.store.cards_by_device[dev_1].add(card_primary)
        self.client.store.cards_by_device[dev_2].add(card_synthetic)

        # Invalidate/refresh blocking index
        self.resolver._device_index_built = False

        # 1. Direct device nexus resolution
        dev_nexus = self.resolver.resolve_device_nexus(dev_1, similarity_threshold=0.75)
        self.assertGreaterEqual(dev_nexus["resolved_links_count"], 1)
        target_devs = [l["target_device"] for l in dev_nexus["resolved_links"]]
        self.assertIn(dev_2, target_devs)
        self.assertIn(card_synthetic, dev_nexus["sybil_cards"])

        # 2. Cardholder sybil discovery
        card_sybils = self.resolver.resolve_cardholder_sybils(card_primary)
        self.assertGreaterEqual(card_sybils["sybil_cards_count"], 1)
        self.assertIn(card_synthetic, card_sybils["sybil_cards"])
        self.assertGreater(card_sybils["sybil_risk_score"], 0.0)

        # 3. REST API testing
        api_resp = self.api_client.post(
            "/api/graph/entity-linkage",
            json={
                "profile_a": {"device_model": "SM-T810", "browser": "chrome 65"},
                "profile_b": {"device_model": "SM-T810", "browser": "chrome 66"},
            },
        )
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.json()
        self.assertGreaterEqual(data["match_probability"], 0.85)
        self.assertEqual(data["verdict"], "CONFIRMED_MATCH")

        sybil_api_resp = self.api_client.post(
            "/api/graph/sybil-check",
            json={"card_id": card_primary},
        )
        self.assertEqual(sybil_api_resp.status_code, 200)
        s_data = sybil_api_resp.json()
        self.assertEqual(s_data["card_id"], card_primary)
        self.assertIn(card_synthetic, s_data["sybil_cards"])

    def test_temporal_isolation_sybil_cards(self):
        """Cards whose transactions occur strictly after as_of must be excluded from sybil links."""
        dev = "SM-T810 Build/NRD90M | Android 7.0 | chrome 67.0.3396.87 | 2048x1536"
        card_past = "card_sybil_past_001"
        card_future = "card_sybil_future_002"

        self.client.store.device_profiles[dev] = parse_device_profile_key(dev)
        self.client.store.devices_by_card[card_past].add(dev)
        self.client.store.devices_by_card[card_future].add(dev)
        self.client.store.cards_by_device[dev].update([card_past, card_future])

        self.client.store.txns_by_card[card_past] = [
            {"transaction_id": "tx_past_1", "card_id": card_past, "epoch_s": 5000}
        ]
        self.client.store.txns_by_card[card_future] = [
            {"transaction_id": "tx_fut_1", "card_id": card_future, "epoch_s": 50000}
        ]

        # Prior to epoch 10000, card_future has no transactions and should not be linked
        nexus = self.resolver.resolve_device_nexus(dev, as_of=10000)
        # Check target links for dev
        for l in nexus["resolved_links"]:
            self.assertNotIn(card_future, l["linked_cards"])


if __name__ == "__main__":
    unittest.main()
