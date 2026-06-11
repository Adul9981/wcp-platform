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
