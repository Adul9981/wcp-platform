"""生成球员信息库 players.json。

范围：只收 Polymarket 球员盘(H2H/参赛/点球/定位球)点名的球星，不贪多。
静态字段为稳定公开事实(所属国家队/位置/是否主罚点球·定位球·是否进攻核心)。
动态字段(伤病/能否参赛)赛前留空，随消息更新——对应深挖报告里的"反向爆冷"机会。

诚实边界：角色字段(点球手等)取广为人知的稳定事实；存疑者保守标 False/None，不臆造。
"""
import json
import os

# (en, zh, team_en, pos, penalty, freekick, main_attacker)
PLAYERS = [
    ("Messi", "梅西", "Argentina", "前锋", True, True, True),
    ("Ronaldo", "C罗", "Portugal", "前锋", True, True, True),
    ("Mbappe", "姆巴佩", "France", "前锋", True, False, True),
    ("Dembele", "登贝莱", "France", "边锋", False, False, False),
    ("Olise", "奥利塞", "France", "边锋", False, False, False),
    ("Yamal", "亚马尔", "Spain", "边锋", False, False, True),
    ("Pedri", "佩德里", "Spain", "中场", False, False, False),
    ("Haaland", "哈兰德", "Norway", "中锋", True, False, True),
    ("Alvarez", "阿尔瓦雷斯", "Argentina", "前锋", False, False, False),
    ("Salah", "萨拉赫", "Egypt", "边锋", True, False, True),
    ("Mane", "马内", "Senegal", "边锋", False, False, True),
    ("Neymar", "内马尔", "Brazil", "前锋", True, True, True),
    ("Vinicius Jr.", "维尼修斯", "Brazil", "边锋", False, False, True),
    ("Valverde", "巴尔韦德", "Uruguay", "中场", False, False, False),
    ("Fernandes", "B费", "Portugal", "中场", True, False, True),
    ("Vitinha", "维蒂尼亚", "Portugal", "中场", False, False, False),
]


def build():
    out = {
        "meta": {
            "scope": "Polymarket球员盘点名的球星",
            "static_note": "所属队/位置/角色为稳定公开事实；存疑保守标False",
            "dynamic_note": "available/injury 赛前留空随消息更新(反向爆冷机会)",
            "generated": "2026-06-11",
        },
        "players": {},
    }
    for en, zh, team, pos, pen, fk, atk in PLAYERS:
        out["players"][en] = {
            "name_en": en, "name_zh": zh, "team": team, "position": pos,
            "penalty_taker": pen, "freekick_taker": fk, "main_attacker": atk,
            "dynamic": {"available": None, "injury_note": "", "last_updated": None},
        }
    return out


if __name__ == "__main__":
    data = build()
    path = os.path.join(os.path.dirname(__file__), "..", "data", "players.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"生成 {len(data['players'])} 名球员 -> {path}")
