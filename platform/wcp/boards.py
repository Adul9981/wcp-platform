"""三榜生成：从 DB 读 topics，评分排序，产出三榜。"""
import json

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
        "title": glossary.translate(t["title"]),   # 中文标题（用户要求#6）
        "title_en": t["title"],                      # 保留原文可追溯（P0.3）
        "line": t["line"],
        "bet_type": t["bet_type"],
        "category": t["category"],
        "price": t["price"],
        "payoff_ratio": scoring.payoff_ratio(t["price"]),
        "volume": t["volume"],
        "liquidity": t["liquidity"],
        "strategy_tags": t["strategy_tags"],
        "direction": t.get("direction"),   # 下注方向(P3)
        "is_new": t["is_new"],
        "kickoff": t["kickoff"],
        "event_url": t["event_url"],
        "snapshot_ts": t["snapshot_ts"],
        "score": score,
        "reason": reason,
    }


def _rank(topics, scorer, top_n, max_per_match=2, max_per_type=4):
    """评分排序 + 多样性控制。
    - 按场次去重(max_per_match)：防同一场多张子盘刷屏。
    - 按盘口类型限量(max_per_type)：防单一类型(如"首开记录")霸榜，呈现多样机会。
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


def generate(conn=None, top_n=15):
    own = conn is None
    conn = conn or db.connect()
    topics = _load_topics(conn)
    boards = {
        "attention": _rank(topics, scoring.score_attention, top_n),
        "overlooked": _rank(topics, scoring.score_overlooked, top_n),
        "payoff": _rank(topics, scoring.score_payoff, top_n),
        "meta": {
            "total_topics": len(topics),
            "disclaimer": "排序基于可观测信号（策略匹配/流动性/成交/盈亏比/新上线），"
                          "未接外部博彩赔率，不含公平价值edge。不构成投资建议。",
        },
    }
    if own:
        conn.close()
    return boards


if __name__ == "__main__":
    b = generate(top_n=5)
    labels = {"attention": "🎯 最值得关注", "overlooked": "💎 最被忽视", "payoff": "📈 最大盈亏比"}
    for key in ("attention", "overlooked", "payoff"):
        print(f"\n==== {labels[key]} ====")
        for i, e in enumerate(b[key], 1):
            print(f"{i}. [{e['line']}/{e['bet_type']}] {e['title'][:36]}")
            print(f"   score={e['score']} | {e['reason']}")
            print(f"   {e['event_url']}")
    print("\n", b["meta"]["disclaimer"])
