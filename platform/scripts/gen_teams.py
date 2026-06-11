"""生成国家队信息库 teams.json（单一真相源）。

数据来源（公开权威，2026-06-10 抓取）：
- 分组：官方 A-L 抽签结果（Wikipedia/NBC/FIFA），并经 Polymarket 赛程反推交叉验证一致
- FIFA 排名：FIFA Men's World Ranking 2026年4月版（ESPN 转载）
- 大洲归属：常识性稳定事实

分级规则（基于 FIFA 排名，文档化、可复算）：
  S=1-7  A=8-19  B=20-35  C=36-50  D=未进前50
静态字段权威；动态字段（积分/出线/伤病/疲劳）赛前为空，随赛程更新。
"""
import json
import os

# (name_en, name_zh, group, confederation, fifa_rank_or_None)
TEAMS = [
    # Group A
    ("Mexico", "墨西哥", "A", "CONCACAF", 15), ("Korea Republic", "韩国", "A", "AFC", 25),
    ("South Africa", "南非", "A", "CAF", None), ("Czechia", "捷克", "A", "UEFA", 41),
    # Group B
    ("Canada", "加拿大", "B", "CONCACAF", 30), ("Switzerland", "瑞士", "B", "UEFA", 19),
    ("Qatar", "卡塔尔", "B", "AFC", None), ("Bosnia and Herzegovina", "波黑", "B", "UEFA", None),
    # Group C
    ("Brazil", "巴西", "C", "CONMEBOL", 6), ("Morocco", "摩洛哥", "C", "CAF", 8),
    ("Haiti", "海地", "C", "CONCACAF", None), ("Scotland", "苏格兰", "C", "UEFA", 43),
    # Group D
    ("United States", "美国", "D", "CONCACAF", 16), ("Paraguay", "巴拉圭", "D", "CONMEBOL", 40),
    ("Australia", "澳大利亚", "D", "AFC", 27), ("Türkiye", "土耳其", "D", "UEFA", 22),
    # Group E
    ("Germany", "德国", "E", "UEFA", 10), ("Curaçao", "库拉索", "E", "CONCACAF", None),
    ("Côte d'Ivoire", "科特迪瓦", "E", "CAF", 34), ("Ecuador", "厄瓜多尔", "E", "CONMEBOL", 23),
    # Group F
    ("Netherlands", "荷兰", "F", "UEFA", 7), ("Sweden", "瑞典", "F", "UEFA", 38),
    ("Tunisia", "突尼斯", "F", "CAF", 44), ("Japan", "日本", "F", "AFC", 18),
    # Group G
    ("Belgium", "比利时", "G", "UEFA", 9), ("Egypt", "埃及", "G", "CAF", 29),
    ("IR Iran", "伊朗", "G", "AFC", 21), ("New Zealand", "新西兰", "G", "OFC", None),
    # Group H
    ("Spain", "西班牙", "H", "UEFA", 2), ("Cabo Verde", "佛得角", "H", "CAF", None),
    ("Saudi Arabia", "沙特阿拉伯", "H", "AFC", None), ("Uruguay", "乌拉圭", "H", "CONMEBOL", 17),
    # Group I
    ("France", "法国", "I", "UEFA", 1), ("Senegal", "塞内加尔", "I", "CAF", 14),
    ("Iraq", "伊拉克", "I", "AFC", None), ("Norway", "挪威", "I", "UEFA", 31),
    # Group J
    ("Argentina", "阿根廷", "J", "CONMEBOL", 3), ("Algeria", "阿尔及利亚", "J", "CAF", 28),
    ("Austria", "奥地利", "J", "UEFA", 24), ("Jordan", "约旦", "J", "AFC", None),
    # Group K
    ("Portugal", "葡萄牙", "K", "UEFA", 5), ("DR Congo", "刚果（金）", "K", "CAF", 46),
    ("Uzbekistan", "乌兹别克斯坦", "K", "AFC", 50), ("Colombia", "哥伦比亚", "K", "CONMEBOL", 13),
    # Group L
    ("England", "英格兰", "L", "UEFA", 4), ("Croatia", "克罗地亚", "L", "UEFA", 11),
    ("Ghana", "加纳", "L", "CAF", None), ("Panama", "巴拿马", "L", "CONCACAF", 33),
]

HOSTS = {"Mexico", "Canada", "United States"}


def tier(rank):
    if rank is None:
        return "D"
    if rank <= 7:
        return "S"
    if rank <= 19:
        return "A"
    if rank <= 35:
        return "B"
    if rank <= 50:
        return "C"
    return "D"


def build():
    out = {
        "meta": {
            "source": "官方抽签(A-L) + FIFA排名2026-04 + Polymarket赛程交叉验证",
            "ranking_version": "2026-04-01",
            "tier_rule": "S=1-7 A=8-19 B=20-35 C=36-50 D=未进前50",
            "generated": "2026-06-10",
            "note": "静态字段权威；动态字段随赛程更新，更新时改 dynamic 区并记 last_updated",
        },
        "teams": {},
    }
    for en, zh, grp, conf, rank in TEAMS:
        out["teams"][en] = {
            "name_en": en, "name_zh": zh, "group": grp, "confederation": conf,
            "fifa_rank": rank, "tier": tier(rank), "is_host": en in HOSTS,
            # —— 动态区：赛前为空，赛程推进时更新 ——
            "dynamic": {
                "played": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0,
                "group_rank": None, "status": "未开赛",  # 未开赛/小组赛中/已出线/已淘汰/已晋级X强
                "recent_form": [], "key_absences": [], "fatigue_note": "",
                "last_updated": None,
            },
        }
    return out


if __name__ == "__main__":
    data = build()
    path = os.path.join(os.path.dirname(__file__), "..", "data", "teams.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    n = len(data["teams"])
    from collections import Counter
    tc = Counter(t["tier"] for t in data["teams"].values())
    cc = Counter(t["confederation"] for t in data["teams"].values())
    print(f"生成 {n} 队 -> {path}")
    print("分级:", dict(sorted(tc.items())))
    print("大洲:", dict(sorted(cc.items())))
    assert n == 48, f"应为48队，实际{n}"
    print("✅ 48队校验通过")
