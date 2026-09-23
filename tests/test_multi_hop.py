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
        self.assertEqual(
            {"顾言", "星桥维修店"},
            entity_terms("user: 顾言在星桥维修店完成了维修。"),
        )
        self.assertEqual(
            {"星桥维修店"}, entity_terms("user: 星桥维修店把取件单放在北门。")
        )
        self.assertEqual(
            {"星桥维修店"}, entity_terms("user: 今天我在星桥维修店等待。")
        )
        self.assertFalse(entity_terms("蛋糕做好后放进冰箱。"))
        self.assertFalse(entity_terms("材料办好后交给同事。"))
        self.assertFalse(entity_terms("已经做好了，明天去领取。"))
        self.assertFalse(entity_terms("我会做好证书。"))
        self.assertFalse(entity_terms("请你做好成品。"))
        self.assertEqual(set(), entity_terms("user: 我在维修店等待。"))

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

    def test_chinese_repeated_names_bridge_without_fixed_sentence_templates(self):
        self.add_all([
            "负责修复我那把旧提琴的师傅叫林澈。",
            "林澈完成修复后委托星桥快递运送提琴。",
            "星桥快递把乐器包裹统一送到音乐学院北门领取点。",
            "我的新吉他由周远调音。",
            "周远使用青禾物流寄送配件。",
            "青禾物流送到南门服务台。",
            "旧提琴的琴盒是深棕色的。",
            "林澈还修复过一把大提琴。",
            "星桥音乐厅周一休息。",
            "北门附近有一家咖啡店。",
            "音乐学院服务台可以借谱架。",
            "提琴修复费用已经支付。",
            "领取乐器需要出示短信。",
            "林澈没有使用青禾物流。",
            "另一个包裹送到了东门驿站。",
        ])
        results = self.store.search(
            "u", "给我修复旧提琴的人最后把琴送到了哪个领取点？", 5
        )
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("师傅叫林澈", contents)
        self.assertIn("林澈完成修复后委托星桥快递", contents)
        self.assertIn("音乐学院北门领取点", contents)

    def test_chinese_transfer_phrase_bridges_maker_courier_and_window(self):
        self.add_all([
            "负责制作我那本资格证书的师傅叫苏衡。",
            "苏衡做好证书后交给岚途快递负责运送。",
            "岚途快递将证件类包裹送到行政楼西侧三号领取窗口。",
            "我的培训证由顾青负责装裱。",
            "顾青把材料交给远山物流。",
            "远山物流送到东门服务台。",
            "资格证书的封皮是深蓝色的。",
            "苏衡还制作过一张纪念卡。",
            "岚途旅行社周日休息。",
            "行政楼西侧有一间会议室。",
            "三号窗口中午暂停办理业务。",
            "证书制作费用已经缴清。",
            "领取证件需要携带身份证。",
            "苏衡没有使用远山物流。",
            "另一个文件送到了北门驿站。",
        ])
        results = self.store.search(
            "u", "制作我那本资格证书的人把成品送到了哪个领取窗口？", 5
        )
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("师傅叫苏衡", contents)
        self.assertIn("苏衡做好证书后交给岚途快递", contents)
        self.assertIn("行政楼西侧三号领取窗口", contents)

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

    def test_english_query_can_follow_discovered_chinese_name_to_schedule(self):
        self.add_all([
            "教我篆刻的老师叫沈禾。",
            "沈禾每周日上午在青石工作室授课。",
            "My watercolor tutor teaches on Tuesday morning.",
            "我以前的篆刻老师叫陈墨。",
            "陈墨每周五下午开课。",
            "青石工作室周日中午关闭。",
            "沈禾周三参加书法社活动。",
            "The lesson desk opens at eight.",
            "篆刻课需要自带印石。",
            "My Chinese language tutor teaches on Monday.",
            "沈荷负责周四的摄影课。",
            "工作室旁边有一家文具店。",
        ])
        results = self.store.search(
            "u", "Which morning does my seal-carving instructor teach?", 5
        )
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("老师叫沈禾", contents)
        self.assertIn("沈禾每周日上午", contents)

    def test_chinese_completed_work_bridges_person_courier_and_destination(self):
        self.add_all([
            "祖传的铜锁由匠人周启修好。",
            "周启完工后托云岭速递寄回铜锁。",
            "云岭速递把贵重包裹放在古城东门保管处领取。",
            "另一把门锁由陈森维修。",
            "陈森交给远帆物流送往西门。",
            "铜锁的钥匙放在木盒里。",
            "云岭景区周一关闭。",
            "东门旁边有一家茶馆。",
            "维修费用已经结清。",
            "领取包裹需要核对短信。",
            "周启没有使用远帆物流。",
            "古城保管处下午五点关门。",
        ])
        results = self.store.search("u", "修好祖传铜锁的人把锁送到哪里领取？", 5)
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("匠人周启修好", contents)
        self.assertIn("周启完工后托云岭速递", contents)
        self.assertIn("古城东门保管处", contents)

    def test_opaque_identifier_enables_bounded_second_relation_hop(self):
        self.add_all([
            "Project Alder stores its flight prototype in the Quartz lab.",
            "The Quartz lab uses access token QA-72.",
            "Mina Cole safeguards access token QA-72.",
            "Project Birch uses the Amber lab.",
            "The Amber lab uses access token AM-19.",
            "Noah Cole manages visitor passes.",
            "The flight prototype demonstration is on Tuesday.",
            "Quartz samples are stored in another building.",
            "The access-token printer is offline.",
            "Project Alder has six design drawings.",
            "Mina Shah reviewed the lab budget.",
            "The lab humidity is checked daily.",
        ])
        results = self.store.search(
            "u", "Who safeguards access to the lab holding Project Alder's prototype?", 5
        )
        contents = "\n".join(result["content"] for result in results)
        self.assertIn("prototype in the Quartz lab", contents)
        self.assertIn("access token QA-72", contents)
        self.assertIn("Mina Cole safeguards", contents)

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
