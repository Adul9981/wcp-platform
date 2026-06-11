"""复盘自动化。

A. 平台预测命中率：自动快照单场方向 → 赛后用 ESPN 赛果判命中 → 按策略统计命中率
B. 用户下注复盘：记录/结算用户实际操作（见 api.py 的 /bets 接口）

诚实：只自动判定可客观结算的单场方向(胜负/大小球)；H2H/长盘等暂标"待定"不强判。
"""
import json
from datetime import datetime, timezone

from . import db, teams


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- A. 预测快照 ----------
def snapshot_predictions(conn, topics):
    """把有方向的单场预测记进 prediction_log（已存在则不覆盖，保留首次记录价）。"""
    rows = []
    for t in topics:
        if t.line != "单场" or not t.direction or not t.match_id:
            continue
        d = t.direction
        if not d.get("outcome"):
            continue   # 无具体选项(如比分文本方向)不入库
        rows.append((t.match_id, d["outcome"], d["label"], t.bet_type,
                     json.dumps(t.strategy_tags, ensure_ascii=False),
                     d.get("price"), t.kickoff, _now()))
    conn.executemany(
        "INSERT OR IGNORE INTO prediction_log"
        "(match_id,predicted,label,bet_type,strategy_tags,price,kickoff,captured_ts)"
        " VALUES(?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ---------- A. 赛果判定 ----------
def _match_key(team_a, team_b):
    """与 normalize.match_id_of 一致地构造场次键的队名部分——这里用队英文名集合匹配。"""
    return frozenset((team_a, team_b))


def resolve_predictions(conn, results):
    """用已完赛结果判定 prediction_log 里"待定"的预测。返回结算数量。"""
    # 构建 完赛结果索引：{frozenset(teamEN,teamEN): (sa, sb, teamA_en, teamB_en)}
    idx = {}
    for r in results:
        ta, tb = teams.get(r["teamA"]), teams.get(r["teamB"])
        if not ta or not tb:
            continue
        idx[_match_key(ta["name_en"], tb["name_en"])] = (
            r["scoreA"], r["scoreB"], ta["name_en"], tb["name_en"])

    pend = conn.execute(
        "SELECT match_id,predicted,bet_type FROM prediction_log WHERE result IS NULL").fetchall()
    settled = 0
    for row in pend:
        verdict, actual = _judge(row["match_id"], row["predicted"], row["bet_type"], idx)
        if verdict is None:
            continue
        conn.execute(
            "UPDATE prediction_log SET result=?,actual=?,settled_ts=? WHERE match_id=? AND predicted=?",
            (verdict, actual, _now(), row["match_id"], row["predicted"]))
        settled += 1
    conn.commit()
    return settled


def _judge(match_id, predicted, bet_type, idx):
    """判定单条预测。返回 (命中/未命中, 实际描述) 或 (None,None) 若无法判定。"""
    # match_id 形如 "mexico-vs-south-africa@2026-06-11"，含队名但已规整；
    # 用预测的 outcome(队英文名/Over/Under) + 在 idx 里按队名子串匹配。
    # 简化：遍历 idx，找 match_id 同时包含两队规整名的那场。
    import re
    def slug(s):
        return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    for key, (sa, sb, ta, tb) in idx.items():
        if slug(ta) in match_id and slug(tb) in match_id:
            total = sa + sb
            actual = f"{ta} {sa}-{sb} {tb}"
            p = predicted.lower()
            if predicted in (ta, tb):                       # 押某队胜
                won = (predicted == ta and sa > sb) or (predicted == tb and sb > sa)
                return ("命中" if won else "未命中"), actual
            if "over" in p or "大" in predicted:            # 押大分
                return ("命中" if total > 2.5 else "未命中"), actual
            if "under" in p or "小" in predicted:           # 押小分
                return ("命中" if total < 2.5 else "未命中"), actual
            return None, None   # 其它方向(比分/H2H)暂不自动判
    return None, None


# ---------- A. 命中率统计 ----------
def hit_rate(conn):
    rows = conn.execute(
        "SELECT strategy_tags,result FROM prediction_log WHERE result IN ('命中','未命中')").fetchall()
    overall = {"命中": 0, "未命中": 0}
    by_strat = {}
    for r in rows:
        overall[r["result"]] += 1
        for s in json.loads(r["strategy_tags"] or "[]"):
            d = by_strat.setdefault(s, {"命中": 0, "未命中": 0})
            d[r["result"]] += 1
    def rate(d):
        n = d["命中"] + d["未命中"]
        return round(d["命中"] / n * 100, 1) if n else None
    return {
        "overall": {**overall, "样本": overall["命中"] + overall["未命中"], "命中率": rate(overall)},
        "by_strategy": {k: {**v, "样本": v["命中"] + v["未命中"], "命中率": rate(v)}
                        for k, v in sorted(by_strat.items())},
        "pending": conn.execute(
            "SELECT COUNT(*) n FROM prediction_log WHERE result IS NULL").fetchone()["n"],
    }
