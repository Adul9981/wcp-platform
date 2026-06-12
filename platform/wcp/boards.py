"""三榜生成：今日关注 / 低风险 / 高风险。

风险分类逻辑（见 3_策略分析库/三榜规则与展示规范.md）：
  今日关注：时间轴，今天开赛的比赛（主区）
  低风险：主张 ≤ 队伍地板（强队确定性/东道主/已出线保守）
  高风险：长赔子区（≤天花板以上）+ 摇摆子区（势均力敌/末轮生死）

原则：低流动不剔除；只靠质量门槛（须有策略依据），不设数量上限。
"""
import json
from datetime import datetime, timezone

from . import db, scoring, glossary


def _load_topics(conn):
    rows = conn.execute("SELECT * FROM topics").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["strategy_tags"] = json.loads(d["strategy_tags"]) if d["strategy_tags"] else []
        d["teams"] = json.loads(d["teams"]) if d["teams"] else []
        dir_raw = d.get("direction")
        d["direction"] = json.loads(dir_raw) if dir_raw and dir_raw != "null" else None
        d["is_new"] = bool(d["is_new"])
        out.append(d)
    return out


def _entry(t, score, reason):
    return {
        "event_id": t["event_id"],
        "title": glossary.translate(t["title"]),
        "title_en": t["title"],
        "line": t["line"],
        "bet_type": t["bet_type"],
        "category": t["category"],
        "price": t["price"],
        "payoff_ratio": scoring.payoff_ratio(t["price"]),
        "volume": t["volume"],
        "liquidity": t["liquidity"],
        "strategy_tags": t["strategy_tags"],
        "direction": t.get("direction"),
        "is_new": t["is_new"],
        "kickoff": t["kickoff"],
        "event_url": t["event_url"],
        "snapshot_ts": t["snapshot_ts"],
        "score": score,
        "reason": reason,
    }


def _rank(topics, scorer, top_n, max_per_match=2, max_per_type=4):
    """评分排序 + 多样性控制。
    注意：多样性控制不剔除低流动——低流动是新上线选题的正常状态，绝不过滤。"""
    scored = []
    for t in topics:
        s, reason = scorer(t)
        if s > 0:
            e = _entry(t, s, reason)
            e["_match_id"] = t["match_id"]
            scored.append(e)
    scored.sort(key=lambda x: x["score"], reverse=True)
    out, per_match, per_type = [], {}, {}
    for e in scored:
        mid = e.pop("_match_id")
        if mid and per_match.get(mid, 0) >= max_per_match:
            continue
        bt = e["bet_type"]
        if per_type.get(bt, 0) >= max_per_type:
            continue
        if mid:
            per_match[mid] = per_match.get(mid, 0) + 1
        per_type[bt] = per_type.get(bt, 0) + 1
        out.append(e)
        if len(out) >= top_n:
            break
    return out


def generate(conn=None, top_n=15, today: str | None = None):
    """生成三榜。today 格式 YYYY-MM-DD（UTC），默认今日。"""
    td = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    own = conn is None
    conn = conn or db.connect()
    topics = _load_topics(conn)

    def _today_scorer(t):
        return scoring.score_today(t, td)

    boards = {
        "today": _rank(topics, _today_scorer, top_n, max_per_match=4, max_per_type=6),
        "low_risk": _rank(topics, scoring.score_low_risk, top_n),
        "high_risk": _rank(topics, scoring.score_high_risk, top_n),
        "meta": {
            "total_topics": len(topics),
            "today": td,
            "disclaimer": "排序基于可观测信号（策略匹配/实力/时间/盈亏比），"
                          "未接外部博彩赔率，不含公平价值edge。不构成投资建议。",
        },
    }
    if own:
        conn.close()
    return boards


if __name__ == "__main__":
    b = generate(top_n=5)
    labels = {"today": "📅 今日关注", "low_risk": "🛡️ 低风险", "high_risk": "🎲 高风险"}
    for key in ("today", "low_risk", "high_risk"):
        print(f"\n==== {labels[key]} ====")
        for i, e in enumerate(b[key], 1):
            pr = e.get("payoff_ratio")
            print(f"{i}. [{e['line']}/{e['bet_type']}] {e['title'][:36]}")
            print(f"   score={e['score']} | 盈亏比={pr}x | {e['reason'][:60]}")
            print(f"   {e['event_url']}")
    print("\n", b["meta"]["disclaimer"])
