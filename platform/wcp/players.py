"""球员信息库加载器 + H2H 进球期望代理评分。

数据源：data/players.json。给球员盘(H2H/参赛/点球)提供方向依据。
"""
import json
import os
from functools import lru_cache

from . import teams

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "players.json")

# Polymarket 标题里的写法 → players.json key 的别名
_ALIASES = {
    "Vinicius Jr": "Vinicius Jr.", "Vinicius": "Vinicius Jr.",
    "Bruno Fernandes": "Fernandes", "Cristiano Ronaldo": "Ronaldo",
    "Lionel Messi": "Messi", "Lamine Yamal": "Yamal", "Kylian Mbappe": "Mbappe",
}


@lru_cache(maxsize=1)
def _load():
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def all_players():
    return _load()["players"]


def get(name):
    name = (name or "").strip()
    ps = all_players()
    if name in ps:
        return ps[name]
    if name in _ALIASES:
        return ps.get(_ALIASES[name])
    return None


_TIER_PTS = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}


def scoring_proxy(name):
    """进球期望代理分(越高越可能进更多球)。诚实：这是启发式代理，非精确预测。

    = 球队走得越远(比赛场次多) + 球员角色越核心。
    """
    p = get(name)
    if not p:
        return None, ""
    tier = teams.tier(p["team"])
    team_pts = _TIER_PTS.get(tier, 1)               # 球队层次=出场场次代理
    role = 0
    if p["main_attacker"]:
        role += 2
    if p["penalty_taker"]:
        role += 1.5
    if p["freekick_taker"]:
        role += 0.5
    score = team_pts + role
    zhteam = teams.get(p["team"])["name_zh"] if teams.get(p["team"]) else p["team"]
    note = f"{p['name_zh']}({zhteam}{tier}级"
    note += "·点球手" if p["penalty_taker"] else ""
    note += "·核心" if p["main_attacker"] else ""
    note += ")"
    return round(score, 1), note


def h2h_pick(player_a, player_b):
    """两球员对决，返回 (赢家name, 依据) 或 (None, '') 若过于接近/缺数据。"""
    sa, na = scoring_proxy(player_a)
    sb, nb = scoring_proxy(player_b)
    if sa is None or sb is None:
        return None, ""
    if abs(sa - sb) < 1.0:          # 太接近，不硬给
        return None, f"{na}≈{nb}，差距过小不推荐"
    win = player_a if sa > sb else player_b
    wn = na if sa > sb else nb
    return win, f"进球期望代理：{wn} 占优（{max(sa,sb)} vs {min(sa,sb)}）"
