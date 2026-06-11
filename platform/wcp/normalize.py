"""归一化：原始 event → Topic；单场盘去重到场次；策略自动打标。

对齐 3_策略分析库/核心策略清单.md 与 1_想法库/核心机会框架.md（策略 A..N）。
打标为规则匹配（MVP）。后续可在 7_优化库 升级。
"""
import re
import json
from datetime import datetime, timezone

from .models import Topic
from . import config, teams


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _first_price(market):
    op = market.get("outcomePrices")
    if not op:
        return None
    try:
        arr = json.loads(op) if isinstance(op, str) else op
        return float(arr[0])
    except (ValueError, TypeError, IndexError):
        return None


# ---- 单场盘：从标题提取对阵与去重键 ----
_VS = re.compile(r"\s+vs\.?\s+", re.IGNORECASE)


def parse_match_title(title: str):
    """返回 (base, teams)。base 去掉 ' - Exact Score'/' - More Markets' 等后缀。"""
    base = title.split(" - ")[0].strip()
    parts = _VS.split(base)
    teams = [p.strip() for p in parts if p.strip()] if len(parts) == 2 else []
    return base, teams


def match_id_of(base: str, kickoff: str | None) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    if kickoff:
        key += "@" + kickoff[:10]   # 同名对阵按日期区分
    return key


# ---- 策略打标 ----
def tag_long(title: str) -> tuple[str, str, list]:
    """长盘 → (category, bet_type, strategy_tags)

    注意（P0.1 不臆造 / P2.1 可解释）：长盘只贴**赛前即成立**的静态策略。
    策略 C（摇摆队末场生死战）是依赖小组积分的动态、单场末轮策略，长盘上无任何
    赛前依据，故不静态贴 C —— 与单场路径 _match_strategies 的"赛前不触发动态策略"
    规则一致（见 7_优化库/策略系统优化项.md P1）。动态 C 仅在单场末轮由真实积分触发。
    """
    t = title.lower()
    if "world cup winner" in t:
        return "01夺冠", "夺冠", ["B"]
    # —— 深挖新增类别(2026-06-11) ——
    if "group" in t and "winner" in t:
        return "11小组头名", "小组头名", ["B"]           # 小组第一：押我方分级最强队(策略B)
    if "continent" in t and "win" in t:
        return "12大洲夺冠", "大洲夺冠", []               # 哪个大洲夺冠：无适用策略（策略E已删）
    if ("will" in t or "play in" in t) and "play in the world cup" in t:
        return "13球员参赛", "球员参赛", []               # 球星是否参赛：无适用策略（策略E已删）
    if "relocated" in t or "moved" in t:
        return "14赛事变动", "赛事变动", []               # 比赛是否移址：政治/花边，无适用策略
    if any(k in t for k in ["golden boot", "top scorer", "goalscorer", "most goal", "most assist", "boot"]):
        return "02射手榜", "射手榜", ["F"]
    if any(k in t for k in ["golden ball", "glove", "clean sheet", "ball winner"]):
        return "03个人奖项", "个人奖项", ["F"]
    if any(k in t for k in ["advance", "reach", "knockout", "round of 16", "quarterfinal", "semifinal", "final"]):
        return "04晋级轮次", "晋级", ["B"]               # 晋级确定性(策略B)；C 不静态贴
    if "stage of elimination" in t:
        return "05各队淘汰阶段", "淘汰阶段", ["B"]        # 各队走多远：强队地板确定性(B)；C 不静态贴
    if any(k in t for k in ["last place", "second place", "group", "highest-scoring", "highest scoring"]):
        return "06小组排名", "小组排名", ["A"]
    if any(k in t for k in ["player to score", "hat trick", "free kick", "penalt", "h2h"]):
        return "07球员表现", "球员", ["F"]
    if any(k in t for k in ["trump", "cry", "photo", "attend"]):
        return "08花边政治", "花边", []
    if any(k in t for k in ["record", "margin", "fastest", "total tournament", "yellow card", "10+"]):
        return "09赛事纪录", "纪录", []
    if any(k in t for k in ["furthest advancing", "worst-placed", "fair play"]):
        return "10大洲其他", "大洲", []
    return "99其他", "", []


def _match_strategies(match_teams: list) -> tuple[list, dict]:
    """基于真实队伍数据判定单场可用策略（替代旧的标题格式硬编码）。

    数据驱动（读 teams.json）：
      A 强打弱：两队分级差 ≥ 2 档
      G 东道主：涉及美/墨/加 且为其主场（东道主必主场）
    势均力敌的非东道主对阵 → 不打标签（这才是正确行为）。
    C/B/I（出线/确定性/保守）依赖小组积分形势，赛前无数据，留待动态更新后再加。
    返回 (tags, evidence) evidence 供可解释展示。
    """
    tags, ev = [], {}
    if len(match_teams) != 2:
        return tags, ev
    a, b = match_teams
    ta, tb = teams.tier(a), teams.tier(b)
    gap = teams.tier_gap(a, b)
    ev["tiers"] = {a: ta, b: tb}
    if gap is not None and gap >= 2:
        tags.append("A")
        strong = a if {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}[ta] < {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}[tb] else b
        ev["A"] = f"分级差{gap}档，强队={teams.get(strong)['name_zh']}"
    host = next((x for x in (a, b) if teams.is_host(x)), None)
    if host:
        tags.append("G")
        ev["G"] = f"东道主={teams.get(host)['name_zh']}主场"

    # —— 动态策略(依赖小组积分/出线状态，赛前为空时不触发) ——
    da = (teams.get(a) or {}).get("dynamic", {})
    db_ = (teams.get(b) or {}).get("dynamic", {})
    sa, sb = da.get("status"), db_.get("status")
    pa, pb = da.get("played", 0), db_.get("played", 0)
    # I 保守踢法小分：一方已出线(末轮可能轮换) → 押小分
    qualified = next((x for x, s in ((a, sa), (b, sb)) if s == "已出线"), None)
    if qualified:
        tags.append("I")
        ev["I"] = f"{teams.get(qualified)['name_zh']}已出线，末轮或轮换→小分"
    # C 摇摆队末场生死战：双方均踢满2场且出线未定 → 生死战，押大分
    if pa == 2 and pb == 2 and sa == "小组赛中" and sb == "小组赛中":
        tags.append("C")
        ev["C"] = "双方末轮生死战，出线未定→大分"
    return tags, ev


def tag_match(title: str, match_teams: list | None = None) -> tuple[str, list, dict]:
    """单场盘 → (bet_type, strategy_tags, evidence)。

    1X2 与 More Markets（含大分/让球）的策略标签**基于真实队伍数据**判定。
    其余衍生盘按盘口类型打标。未识别者不强行套标签（防污染榜单）。
    """
    t = title.lower()
    has_suffix = " - " in title
    mt = match_teams or []
    if "exact score" in t:
        # 准确比分(F)：强弱悬殊时高赔价值最大
        gap = teams.tier_gap(mt[0], mt[1]) if len(mt) == 2 else None
        return "比分", (["F"] if (gap or 0) >= 2 else ["F"]), {}
    if "more markets" in t:
        # 综合盘含大分/让球：A 由真实分级差决定
        tags, ev = _match_strategies(mt)
        return "综合(含O/U/让球/BTTS)", tags, ev
    if "h2h" in t:
        return "球员H2H", ["F"], {}
    if "both teams to score" in t or "btts" in t:
        return "BTTS", [], {}
    if "corner" in t:
        return "角球", ["F"], {}
    if "first" in t and "score" in t:
        return "首开记录", [], {}
    if any(k in t for k in ["halftime", "half-time", "1st half", "first half"]):
        return "半场", [], {}
    if "to advance" in t or "to qualify" in t:
        return "出线", ["B"], {}      # 出线确定性(策略B)；C 是动态末轮策略，不静态贴
    if not has_suffix:
        tags, ev = _match_strategies(mt)     # 裸对阵 1X2：数据驱动打标
        return "1X2", tags, ev
    return "其他衍生", [], {}


# ---- 主转换 ----
def _extract_outcomes(markets: list) -> list:
    """从子市场抽取选项及其 Yes 概率：[{name, price}]。
    单场1X2 每个选项是独立二元市场(groupItemTitle=选项名, price[0]=Yes概率)。"""
    outs = []
    for m in markets:
        name = m.get("groupItemTitle") or m.get("question") or ""
        p = _first_price(m)
        if name and p is not None:
            outs.append({"name": name.strip(), "price": p})
    return outs


def event_to_topic(ev: dict, line: str, ts: str) -> Topic:
    title = ev.get("title") or ""
    slug = ev.get("slug") or ""
    markets = ev.get("markets") or []
    price = _first_price(markets[0]) if markets else None
    outcomes = _extract_outcomes(markets)

    # line 数据驱动：标题含 "X vs Y" 即单场盘（新 umbrella tag 混合了单场与长盘）
    _, _vs_teams = parse_match_title(title)
    line = "单场" if len(_vs_teams) == 2 else "长盘"

    if line == "单场":
        base, match_teams = parse_match_title(title)
        kickoff = ev.get("startTime") or ev.get("endDate")
        mid = match_id_of(base, kickoff)
        bet_type, tags, _ev = tag_match(title, match_teams)
        category = "单场比赛"
    else:
        match_teams = []
        kickoff = None
        mid = None
        category, bet_type, tags = tag_long(title)

    return Topic(
        event_id=str(ev.get("id")),
        slug=slug,
        title=title,
        line=line,
        category=category,
        match_id=mid,
        teams=match_teams,
        bet_type=bet_type,
        strategy_tags=tags,
        price=price,
        outcomes=outcomes,
        volume=float(ev.get("volume", 0) or 0),
        liquidity=float(ev.get("liquidity", 0) or 0),
        kickoff=kickoff,
        snapshot_ts=ts,
        event_url=config.build_event_url(slug),
    )


def build_topics(long_events, match_events) -> tuple[list, dict]:
    ts = _now_iso()
    topics = [event_to_topic(e, "长盘", ts) for e in long_events]
    topics += [event_to_topic(e, "单场", ts) for e in match_events]

    # 单场盘去重统计：多少独立场次
    match_ids = {t.match_id for t in topics if t.line == "单场" and t.match_id}
    stats = {
        "long_count": len(long_events),
        "match_event_count": len(match_events),
        "distinct_matches": len(match_ids),
        "ts": ts,
    }
    return topics, stats
