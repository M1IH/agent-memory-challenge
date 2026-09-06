import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig, entity_terms


class MultiHopRetrievalTests(unittest.TestCase):
    def test_conservative_chinese_entity_extraction(self):
        self.assertEqual({"许舟"}, entity_terms("修好键盘的师傅叫许舟。"))
        self.assertEqual(
            {"许舟", "云帆快递"}, entity_terms("user: 许舟寄回时使用了云帆快递。")
        )
        self.assertEqual(
            {"云帆快递"}, entity_terms("user: 云帆快递统一投放到三号柜。")
        )

    def test_chinese_two_hop_chain_keeps_bridge_and_destination(self):
        self.add_all([
            "修好我蓝色机械键盘的师傅叫许舟。",
            "许舟寄回键盘时使用了云帆快递。",
            "云帆快递统一投放到东区三号取件柜。",
            "蓝色机械键盘使用青轴。",
            "另一把键盘送到了南门便利店。",
            "机械键盘的备用键帽在抽屉里。",
            "我考虑自己修蓝色键盘，但没有拆开。",
            "蓝色键盘不是在校内维修的。",
            "打印店老板也叫许舟。",
            "我的黑色薄膜键盘由周越修理。",
        ])
        results = self.store.search(
            "u", "给我修蓝色机械键盘的师傅把它送到了哪个取件柜？", 5
        )
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("师傅叫许舟", contents)
        self.assertIn("许舟寄回键盘", contents)
        self.assertIn("东区三号取件柜", contents)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.directory.name) / "test.db", embedder=False)

    def tearDown(self):
        self.directory.cleanup()

    def add_all(self, contents):
        for index, content in enumerate(contents):
            self.store.add(str(index), "u", "s", [{"role": "user", "content": content}])

    def test_manager_identity_bridges_to_schedule(self):
        self.add_all([
            "My manager is Priya Nair.",
            "The design manager runs a weekly review on Monday.",
            "The sales manager runs a weekly review on Tuesday.",
            "The operations manager runs a weekly review on Wednesday.",
            "The finance manager runs a weekly review on Friday.",
            "Priya Nair holds her team check-in every Thursday.",
            "Priya Shah holds her team check-in every Wednesday.",
            "My former manager was Daniel Wu.",
            "Daniel Wu holds his weekly review on Monday.",
            "My manager's monthly budget review is on the first Friday.",
            "The weekly review presentation uses a blue title slide.",
            "My weekly review notes are stored in the shared folder.",
        ])
        results = self.store.search("u", "On which day is the weekly review run by my manager?", 5)
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("My manager is Priya Nair", contents)
        self.assertIn("Priya Nair holds her team check-in every Thursday", contents)

    def test_project_room_bridges_to_key_holder(self):
        self.add_all([
            "Project Juniper was assigned the Cedar room.",
            "Project Juniper's owner is Lena.",
            "Project Juniper's budget reviewer is Omar.",
            "Lena keeps the key to the Maple room.",
            "Omar keeps the key to the Willow room.",
            "Project Birch was assigned the Maple room.",
            "The Cedar room has a whiteboard and six chairs.",
            "The Cedar room key is held by Mei Chen.",
            "Mei Lin keeps the key to the Elm room.",
            "Project Juniper's room booking request was approved.",
            "The Juniper room key is held by Alex. It is not the Cedar room.",
            "Project Juniper's launch checklist includes a room booking.",
        ])
        results = self.store.search("u", "Who keeps the key to the room assigned to Project Juniper?", 5)
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("Project Juniper was assigned the Cedar room", contents)
        self.assertIn("The Cedar room key is held by Mei Chen", contents)

    def test_linkage_can_be_disabled_for_ablation(self):
        store = MemoryStore(
            Path(self.directory.name) / "disabled.db", embedder=False,
            retrieval_config=RetrievalConfig(linkage_enabled=False),
        )
        store.add("a", "u", "s", [{"role": "user", "content": "My manager is Priya Nair."}])
        store.add("b", "u", "s", [{"role": "user", "content": "Priya Nair holds her team check-in every Thursday."}])
        results = store.search("u", "When is my manager's weekly review?", 1)
        self.assertNotIn("Thursday", results[0]["content"])
