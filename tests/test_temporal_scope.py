import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig


class TemporalScopeTests(unittest.TestCase):
    def test_current_comparison_query_uses_current_session_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            rows = [
                ("old", "Previously Maren's ceramics studio occupied the old warehouse."),
                ("old", "The address was 7 Dock Street."),
                ("new", "Maren's ceramics studio changed premises; this is her current studio."),
                ("new", "The new address is 42 Alder Lane."),
            ]
            for index, (session, content) in enumerate(rows):
                store.add(str(index), "u", session, [{
                    "role": "user", "content": content, "timestamp": 1000 + index,
                }])
            for index in range(8):
                store.add(f"noise-{index}", "u", f"noise-{index}", [{
                    "role": "user", "content": f"Unrelated archive note {index}.",
                }])

            results = store.search(
                "u",
                "Where is Maren's ceramics studio now, compared with where it was previously?",
                2,
            )

            self.assertIn("current studio", results[0]["content"])
            self.assertIn("42 Alder Lane", results[1]["content"])

    def test_chinese_current_comparison_uses_current_session_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            rows = [
                ("old", "原来云杉书店登记过新书配送的旧安排。"),
                ("old", "当时交给远山物流运输。"),
                ("new", "云杉书店的新书配送后来换成新的合作方，目前按新合同执行。"),
                ("new", "合同签给了青鸟物流，由他们送货。"),
            ]
            for index, (session, content) in enumerate(rows):
                store.add(str(index), "u", session, [{
                    "role": "user", "content": content, "timestamp": 1000 + index,
                }])
            for index in range(8):
                store.add(f"noise-{index}", "u", f"noise-{index}", [{
                    "role": "user", "content": f"无关档案记录{index}。",
                }])

            results = store.search(
                "u", "对比原来的安排，云杉书店目前由哪家公司配送新书？", 3,
            )

            self.assertTrue(any("青鸟物流" in item["content"] for item in results[:2]))
            self.assertFalse(any("远山物流" in item["content"] for item in results[:2]))

    def test_temporal_ablation_keeps_session_window_without_historical_seed_bias(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            store = MemoryStore(database, embedder=False)
            rows = [
                ("contract", "The bakery flour supplier contract changed suppliers."),
                ("contract", "The invoice reference is AMBER."),
                ("lunch", "Previously the bakery met for lunch."),
                ("lunch", "The menu reference is VIOLET."),
            ] + [(f"noise-{i}", f"Unrelated traffic bulletin {i}.") for i in range(8)]
            for index, (session, content) in enumerate(rows):
                store.add(str(index), "u", session, [{
                    "role": "user", "content": content, "timestamp": 1000 + index,
                }])
            query = "Which flour supplier did the bakery use before it changed suppliers?"
            ablated = MemoryStore(database, embedder=False, retrieval_config=RetrievalConfig(
                temporal_enabled=False, linkage_enabled=False,
            ))
            results = ablated.search("u", query, 2)
            self.assertIn("supplier contract", results[0]["content"])
            self.assertIn("AMBER", results[1]["content"])

            without_window = MemoryStore(database, embedder=False, retrieval_config=RetrievalConfig(
                temporal_enabled=False, linkage_enabled=False, session_window_enabled=False,
            ))
            self.assertFalse(any("AMBER" in item["content"]
                                 for item in without_window.search("u", query, 2)))

    def test_unrelated_updates_do_not_displace_topic_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            store.add("desk", "u", "s", [{"role": "user", "content": "My current desk location is Room-204.", "timestamp": 1000}])
            for index, topic in enumerate(("lunch", "wallpaper", "music", "breakfast", "route", "phone")):
                store.add(str(index), "u", "s", [{"role": "user", "content": f"My current {topic} changed to blue.", "timestamp": 2000 + index}])
            result = store.search("u", "What is my current desk location?", 1)
            self.assertIn("Room-204", result[0]["content"])

    def test_unrelated_updated_fact_is_not_returned_by_lexical_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            store.add("r", "u", "s", [{"role": "user", "content": "Lunch changed to soup."}])
            self.assertEqual([], store.search("u", "current desk location", 5))

    def test_chinese_grammatical_overlap_is_not_a_topic(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            store.add("a", "u", "s", [{"role": "user", "content": "我现在的工位在三楼。", "timestamp": 1000}])
            store.add("b", "u", "s", [{"role": "user", "content": "我现在的午餐改成面条。", "timestamp": 2000}])
            self.assertIn("三楼", store.search("u", "我现在的工位在哪里？", 1)[0]["content"])

    def test_same_topic_update_without_timestamp_still_gets_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "test.db", embedder=False)
            store.add("a", "u", "s", [{"role": "user", "content": "My current breakfast is toast."}])
            store.add("b", "u", "s", [{"role": "user", "content": "My breakfast changed to oatmeal."}])
            self.assertIn("oatmeal", store.search("u", "What is my current breakfast?", 1)[0]["content"])
