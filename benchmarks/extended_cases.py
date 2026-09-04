from __future__ import annotations


def build_extended_cases() -> list[dict]:
    """Build 100 deterministic, synthetic cases without competition data."""
    cases: list[dict] = []
    names = ["Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper", "Indigo", "Jules"]
    cities = ["Lisbon", "Oslo", "Kyoto", "Lima", "Accra", "Tallinn", "Perth", "Quito", "Riga", "Busan"]
    foods = ["mango", "olive", "ginger", "papaya", "walnut", "radish", "lentil", "peach", "barley", "fig"]
    zh_items = ["紫砂壶", "折叠伞", "咖啡磨豆机", "登山杖", "蓝牙音箱", "机械键盘", "空气炸锅", "保温杯", "露营灯", "拍立得"]

    for i in range(10):
        base = 1_704_067_200_000 + i * 86_400_000
        cases.extend([
            {
                "name": f"extended_direct_en_{i}", "category": "direct_fact",
                "memories": [{"content": f"My project mentor is {names[i]}.", "timestamp": base},
                             {"content": f"I read an article about {cities[(i + 1) % 10]}.", "timestamp": base + 1}],
                "query": "Who is my project mentor?", "expected": names[i],
            },
            {
                "name": f"extended_direct_zh_{i}", "category": "direct_fact",
                "memories": [{"content": f"我新买的东西是{zh_items[i]}", "timestamp": base},
                             {"content": "周末需要整理储物柜", "timestamp": base + 1}],
                "query": "我新买了什么东西？", "expected": zh_items[i],
            },
            {
                "name": f"extended_options_{i}", "category": "multiple_choice",
                "memories": [{"content": f"The locker code word is {foods[i]}.", "timestamp": base},
                             {"content": "The cafeteria menu changes weekly.", "timestamp": base + 1}],
                "query": "What is the locker code word?",
                "options": ["A. river", f"B. {foods[i]}", "C. cloud", "D. stone"], "expected": foods[i],
            },
            {
                "name": f"extended_temporal_{i}", "category": "temporal_update",
                "memories": [{"content": f"I currently live in {cities[(i + 1) % 10]}.", "timestamp": base},
                             {"content": f"I later moved and now live in {cities[i]}.", "timestamp": base + 100_000}],
                "query": "Where do I live now?", "expected": cities[i],
            },
            {
                "name": f"extended_noise_{i}", "category": "noise_resistance",
                "memories": [{"content": f"My allergy alert ingredient is {foods[i]}.", "timestamp": base},
                             {"content": f"A market display mentioned {foods[i]} colored labels.", "timestamp": base + 1},
                             {"content": "The travel checklist is stored in a blue folder.", "timestamp": base + 2}],
                "query": "Which ingredient is on my allergy alert?", "expected": f"ingredient is {foods[i]}",
            },
            {
                "name": f"extended_multi_hop_{i}", "category": "multi_hop",
                "memories": [{"content": f"My teammate is {names[i]}.", "timestamp": base},
                             {"content": f"{names[i]} relocated to {cities[i]}." , "timestamp": base + 1},
                             {"content": f"Another team visited {cities[(i + 1) % 10]}." , "timestamp": base + 2}],
                "query": "Where does my teammate live?",
                "expected_all": [f"teammate is {names[i]}", f"{names[i]} relocated to {cities[i]}"],
            },
            {
                "name": f"extended_list_{i}", "category": "list_recall",
                "memories": [{"content": f"I started yoga group {i} on Mondays.", "timestamp": base},
                             {"content": f"I joined chess club {i} on Wednesdays.", "timestamp": base + 1},
                             {"content": f"I volunteer at shelter {i} on Saturdays.", "timestamp": base + 2},
                             {"content": f"My neighbor plays tennis team {i}.", "timestamp": base + 3}],
                "query": "What weekly activities did I start?",
                "expected_all": [f"yoga group {i}", f"chess club {i}", f"shelter {i}"],
            },
            {
                "name": f"extended_privacy_{i}", "category": "rules_privacy",
                "memories": [{"content": f"Before publishing report {i}, remove all phone numbers.", "timestamp": base},
                             {"content": f"Report {i} uses the green cover template.", "timestamp": base + 1}],
                "query": f"What privacy step applies before publishing report {i}?", "expected": "remove all phone numbers",
            },
            {
                "name": f"extended_coreference_{i}", "category": "multi_turn", "single_add": True,
                "memories": [{"role": "user", "content": f"My coordinator is {names[i]}.", "timestamp": base},
                             {"role": "assistant", "content": f"They scheduled checkpoint {i} for Friday.", "timestamp": base + 1}],
                "query": f"When is {names[i]}'s checkpoint {i}?",
                "expected_all": [f"coordinator is {names[i]}", f"checkpoint {i} for Friday"],
            },
            {
                "name": f"extended_cross_language_{i}", "category": "cross_language",
                "memories": [{"content": f"My preferred travel city is {cities[i]}.", "timestamp": base},
                             {"content": "I keep old tickets in a drawer.", "timestamp": base + 1}],
                "query": "我最想去哪个城市旅行？", "expected": cities[i],
            },
        ])
    return cases
