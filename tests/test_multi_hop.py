import tempfile
import unittest
from pathlib import Path

from app.store import MemoryStore, RetrievalConfig


class MultiHopRetrievalTests(unittest.TestCase):
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
