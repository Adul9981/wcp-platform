"""国家队信息库加载器（活数据，随赛程更新）。

数据源：data/teams.json（由 scripts/gen_teams.py 生成，权威静态字段 + 动态区）。
其他模块通过这里读取队伍分级/东道主/大洲/出线形势，给策略打标提供真实依据，
替代旧的"按标题格式硬编码标签"。
"""
import json
import os
from functools import lru_cache

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "teams.json")

# 中文名 → 英文 key 反查（前端传中文时用）
@lru_cache(maxsize=1)
def _load():
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


def all_teams():
    return _load()["teams"]


def meta():
    return _load()["meta"]


@lru_cache(maxsize=1)
def _zh_index():
    return {t["name_zh"]: en for en, t in all_teams().items()}


# Polymarket 与官方写法差异的别名映射
_ALIASES = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Ivory Coast": "Côte d'Ivoire",
    "South Korea": "Korea Republic",
    "Iran": "IR Iran",
    "Turkiye": "Türkiye",
    "USA": "United States",
    "Cape Verde": "Cabo Verde",
}


def get(name):
    """按英文名/别名/中文名取队伍记录，找不到返回 None。"""
    teams = all_teams()
    if name in teams:
        return teams[name]
    if name in _ALIASES:
        return teams.get(_ALIASES[name])
    en = _zh_index().get(name)
    return teams.get(en) if en else None


def tier(name):
    t = get(name)
    return t["tier"] if t else None


def is_host(name):
    t = get(name)
    return bool(t and t["is_host"])


def group_of(name):
    t = get(name)
    return t["group"] if t else None


def tier_gap(a, b):
    """两队分级差（档数）。S=0,A=1,B=2,C=3,D=4。找不到返回 None。"""
    order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}
    ta, tb = tier(a), tier(b)
    if ta is None or tb is None:
        return None
    return abs(order[ta] - order[tb])


# 分级 → 阶段预期整数（teams.json 补入 stage_floor/stage_ceiling 前的代理）
# 值越大 = 阶段越高：5=冠军 4=决赛 3=四强 2=八强 1=十六强 0=小组出线 -1=小组出局
_TIER_FLOOR = {"S": 3, "A": 2, "B": 1, "C": 0, "D": -1}   # 该级别"应该"到达的最低阶段
_TIER_CEIL  = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}    # 高于此 = 长赔区


def stage_floor_int(name: str) -> int | None:
    """队伍地板阶段整数（S→四强3, A→八强2, B→十六强1, C→出线0, D→小组出局-1）。"""
    t = get(name)
    return _TIER_FLOOR.get(t["tier"]) if t else None


def stage_ceil_int(name: str) -> int | None:
    """队伍天花板阶段整数（高于此 = 长赔超预期区）。"""
    t = get(name)
    return _TIER_CEIL.get(t["tier"]) if t else None


def groups():
    """按组聚合：{'A': [team,...], ...}"""
    out = {}
    for en, t in all_teams().items():
        out.setdefault(t["group"], []).append(t)
    for g in out.values():
        g.sort(key=lambda x: (x["fifa_rank"] is None, x["fifa_rank"] or 999))
    return dict(sorted(out.items()))


if __name__ == "__main__":
    print("信息库:", meta()["source"])
    for g, ts in groups().items():
        line = "  ".join(f"{t['name_zh']}({t['tier']}{t['fifa_rank'] or '-'})"
                         + ("🏠" if t["is_host"] else "") for t in ts)
        print(f"组{g}: {line}")
