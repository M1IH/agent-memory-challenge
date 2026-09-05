import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig, semantic_expansion_terms, tokenize


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(
            Path(self.temp_dir.name) / "test.db", embedder=False
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def add(self, user_id, request_id, content, timestamp=1704067200000):
        self.store.add(
            request_id=request_id,
            user_id=user_id,
            session_id="session-1",
            messages=[{"role": "user", "content": content, "timestamp": timestamp}],
        )

    def test_chinese_tokenizer_keeps_bigrams(self):
        tokens = tokenize("我喜欢乌龙茶")
        self.assertIn("乌龙", tokens)
        self.assertIn("龙茶", tokens)

    def test_search_returns_relevant_memory_first(self):
        self.add("alice", "req-1", "我最喜欢喝乌龙茶")
        self.add("alice", "req-2", "我周末喜欢爬山")
        results = self.store.search("alice", "我喜欢喝什么茶", 10)
        self.assertTrue(results)
        self.assertIn("乌龙茶", results[0]["content"])

    def test_user_ids_are_strictly_isolated(self):
        self.add("alice", "req-1", "秘密代号是蓝鲸")
        self.add("bob", "req-2", "Bob 喜欢苹果")
        results = self.store.search("bob", "秘密代号是什么", 10)
        self.assertFalse(any("蓝鲸" in item["content"] for item in results))

    def test_repeated_add_is_idempotent(self):
        self.add("alice", "req-1", "我喜欢乌龙茶")
        self.add("alice", "req-1", "我喜欢乌龙茶")
        results = self.store.search("alice", "乌龙茶", 10)
        self.assertEqual(1, len(results))

    def test_options_help_retrieve_choice_evidence(self):
        self.add("alice", "req-1", "我最喜欢的饮料是乌龙茶")
        results = self.store.search(
            "alice", "我喜欢哪一种饮料", 10,
            options=["A. 咖啡", "B. 乌龙茶"],
        )
        self.assertIn("乌龙茶", results[0]["content"])

    def test_many_distractor_options_do_not_overwhelm_query(self):
        self.add("alice", "req-1", "我的宠物名字叫豆包")
        self.add("alice", "req-2", "雪球、咖啡、北京和蓝色是会议中的候选词")
        results = self.store.search(
            "alice", "我的宠物叫什么名字", 10,
            options=["A. 雪球", "B. 咖啡", "C. 北京", "D. 豆包"],
        )
        self.assertIn("豆包", results[0]["content"])

    def test_option_labels_are_not_treated_as_evidence(self):
        self.add("alice", "req-1", "A 是项目内部的临时代号")
        self.add("alice", "req-2", "我最喜欢的水果是芒果")
        results = self.store.search(
            "alice", "我最喜欢什么水果", 10,
            options=["A. 苹果", "B. 芒果"],
        )
        self.assertIn("芒果", results[0]["content"])

    def test_semantic_expansion_connects_common_paraphrases(self):
        terms = semantic_expansion_terms("我最近添置的厨具是什么")
        self.assertIn("入手", terms)
        self.assertIn("购买", terms)

    def test_semantic_expansion_connects_residence_and_avoidance_phrases(self):
        residence_terms = semantic_expansion_terms("Which city do I live in now?")
        avoidance_terms = semantic_expansion_terms(
            "Which ingredient should a recommendation avoid?"
        )
        self.assertIn("relocated", residence_terms)
        self.assertIn("cannot", avoidance_terms)
        self.assertIn("stand", avoidance_terms)

    def test_current_question_prefers_later_updated_memory(self):
        self.add("alice", "req-1", "我现在最喜欢的早餐是豆浆油条", 1704067200000)
        self.add("alice", "req-2", "后来口味变了，早餐首选燕麦酸奶", 1735689600000)
        results = self.store.search("alice", "我现在最喜欢什么早餐", 10)
        self.assertIn("燕麦酸奶", results[0]["content"])

    def test_temporal_ablation_switch_removes_update_preference(self):
        self.add("alice", "req-1", "My current desk location is Room-101.", 1704067200000)
        self.add("alice", "req-2", "Later, it changed to Room-202.", 1704067300000)
        self.assertIn("Room-202", self.store.search("alice", "What is my current desk location?", 1)[0]["content"])
        ablated = MemoryStore(
            Path(self.temp_dir.name) / "test.db",
            embedder=False,
            retrieval_config=RetrievalConfig(temporal_enabled=False),
        )
        result = ablated.search("alice", "What is my current desk location?", 1)
        self.assertIn("Room-101", result[0]["content"])

    def test_returned_memory_carries_timestamp_and_role(self):
        self.add("alice", "req-1", "周六去图书馆", 1704067200000)
        result = self.store.search("alice", "周六去哪里", 1)[0]
        self.assertTrue(result["content"].startswith("[2024-01-01T00:00:00Z] user: "))

    def test_message_keeps_previous_turn_for_pronoun_resolution(self):
        self.store.add(
            request_id="req-context",
            user_id="alice",
            session_id="session-context",
            messages=[
                {
                    "role": "user",
                    "content": "My new manager is Priya.",
                    "timestamp": 1704067200000,
                },
                {
                    "role": "assistant",
                    "content": "She moved the weekly review to Thursday.",
                    "timestamp": 1704067260000,
                },
            ],
        )
        result = self.store.search(
            "alice", "When is Priya's weekly review?", 1
        )[0]
        self.assertIn("My new manager is Priya", result["content"])
        self.assertIn("weekly review to Thursday", result["content"])


if __name__ == "__main__":
    unittest.main()
