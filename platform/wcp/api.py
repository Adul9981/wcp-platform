"""FastAPI 服务层 —— 暴露三榜与选题数据。

运行: uvicorn wcp.api:app --reload
原则 P0.2：响应带 snapshot 时间；P2.1：每条带 reason 可解释。
"""
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse

from pydantic import BaseModel
from . import db, boards, glossary, reference, scheduler, review, copywriting


@asynccontextmanager
async def lifespan(app):
    db.init_db()           # 冷启动先建表(线上无DB时防 500)
    scheduler.start()      # 启动后台数据自动刷新(启动即跑一次填充数据)
    yield
    scheduler.stop()


app = FastAPI(title="WCP 世界杯预测平台 API", version="0.4", lifespan=lifespan)

_STATIC = os.path.join(os.path.dirname(__file__), "static")


@app.get("/")
def home():
    """单页仪表盘（三榜可视化）。"""
    return FileResponse(os.path.join(_STATIC, "index.html"))


def _row_to_topic(r):
    d = dict(r)
    d["strategy_tags"] = json.loads(d["strategy_tags"]) if d["strategy_tags"] else []
    d["teams"] = json.loads(d["teams"]) if d["teams"] else []
    d["teams_zh"] = [glossary.team_zh(x) for x in d["teams"]]
    d["is_new"] = bool(d["is_new"])
    d["title_en"] = d["title"]
    d["title"] = glossary.translate(d["title"])   # 中文标题（要求#6）
    return d


@app.get("/health")
def health():
    conn = db.connect()
    try:
        row = conn.execute("SELECT COUNT(*) n, MAX(snapshot_ts) ts FROM topics").fetchone()
        return {"status": "ok", "topics": row["n"], "last_snapshot": row["ts"]}
    finally:
        conn.close()


# ---------- 文案系统 ----------
@app.get("/copy")
def get_copy():
    conn = db.connect()
    try:
        return {"pieces": copywriting.generate_all(conn)}
    finally:
        conn.close()


# ---------- 复盘A：平台预测命中率 ----------
@app.get("/review/predictions")
def review_predictions():
    conn = db.connect()
    try:
        return review.hit_rate(conn)
    finally:
        conn.close()


# ---------- 复盘B：用户下注日志 ----------
class BetIn(BaseModel):
    event_id: str = ""
    title: str
    direction: str
    stake: float
    price: float | None = None
    note: str = ""


class SettleIn(BaseModel):
    status: str            # won / lost / void
    pnl: float | None = None


@app.get("/bets")
def list_bets():
    conn = db.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM bet_log ORDER BY created_ts DESC").fetchall()]
        staked = sum(r["stake"] or 0 for r in rows)
        pnl = sum(r["pnl"] or 0 for r in rows if r["status"] in ("won", "lost", "void"))
        settled = [r for r in rows if r["status"] in ("won", "lost")]
        wins = sum(1 for r in settled if r["status"] == "won")
        return {"bets": rows, "summary": {
            "总注数": len(rows), "总投入": round(staked, 2),
            "已结算": len(settled), "胜": wins,
            "胜率": round(wins / len(settled) * 100, 1) if settled else None,
            "总盈亏": round(pnl, 2),
            "回报率": round(pnl / staked * 100, 1) if staked else None,
        }}
    finally:
        conn.close()


@app.post("/bets")
def add_bet(b: BetIn):
    from datetime import datetime, timezone
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO bet_log(event_id,title,direction,stake,price,note,created_ts)"
            " VALUES(?,?,?,?,?,?,?)",
            (b.event_id, b.title, b.direction, b.stake, b.price, b.note,
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


@app.post("/bets/{bet_id}/settle")
def settle_bet(bet_id: int, s: SettleIn):
    from datetime import datetime, timezone
    conn = db.connect()
    try:
        row = conn.execute("SELECT stake,price FROM bet_log WHERE id=?", (bet_id,)).fetchone()
        if not row:
            raise HTTPException(404, "注单不存在")
        pnl = s.pnl
        if pnl is None:   # 自动算盈亏：赢=投入×(1/price-1)，输=-投入
            if s.status == "won" and row["price"]:
                pnl = round(row["stake"] * (1 / row["price"] - 1), 2)
            elif s.status == "lost":
                pnl = -row["stake"]
            else:
                pnl = 0
        conn.execute("UPDATE bet_log SET status=?,pnl=?,settled_ts=? WHERE id=?",
                     (s.status, pnl, datetime.now(timezone.utc).isoformat(), bet_id))
        conn.commit()
        return {"ok": True, "pnl": pnl}
    finally:
        conn.close()


@app.delete("/bets/{bet_id}")
def delete_bet(bet_id: int):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM bet_log WHERE id=?", (bet_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/standings")
def standings():
    """小组积分榜 + 出线形势（动态数据闭环）。"""
    from . import teams as tm
    out = {}
    for g, ts in tm.groups().items():
        rows = []
        for t in ts:
            d = t.get("dynamic", {})
            rows.append({
                "team": t["name_zh"], "tier": t["tier"], "is_host": t["is_host"],
                "played": d.get("played", 0), "w": d.get("w", 0), "d": d.get("d", 0),
                "l": d.get("l", 0), "gf": d.get("gf", 0), "ga": d.get("ga", 0),
                "pts": d.get("pts", 0), "rank": d.get("group_rank"),
                "status": d.get("status", "未开赛"),
            })
        rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 99))
        out[g] = rows
    return {"groups": out, "last_updated": next(
        (t["dynamic"].get("last_updated") for t in tm.all_teams().values()
         if t["dynamic"].get("last_updated")), None)}


@app.get("/refresh-status")
def refresh_status():
    """数据自动刷新状态（P0.4 失败可见）。"""
    return scheduler.status


@app.post("/refresh")
def refresh_now():
    """手动立即刷新一次数据。"""
    try:
        return {"ok": True, "result": scheduler.run_once()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"刷新失败: {type(e).__name__}: {e}")


@app.get("/boards")
def get_boards(top_n: int = Query(15, ge=1, le=50)):
    """三榜：最值得关注 / 最被忽视 / 最大盈亏比。"""
    return boards.generate(top_n=top_n)


@app.get("/strategies")
def get_strategies():
    """策略说明（要求#4）。"""
    return reference.STRATEGIES


@app.get("/progress")
def get_progress(today: str | None = None):
    """世界杯赛程进度纵览（要求#3）。"""
    return reference.progress(today)


@app.get("/topics")
def list_topics(
    line: str | None = Query(None, description="长盘 / 单场"),
    strategy: str | None = Query(None, description="策略标签 A..N"),
    is_new: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = 0,
):
    conn = db.connect()
    try:
        sql = "SELECT * FROM topics WHERE 1=1"
        args = []
        if line:
            sql += " AND line=?"; args.append(line)
        if is_new is not None:
            sql += " AND is_new=?"; args.append(int(is_new))
        if strategy:
            sql += " AND strategy_tags LIKE ?"; args.append(f'%"{strategy}"%')
        sql += " ORDER BY volume DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        rows = conn.execute(sql, args).fetchall()
        return {"count": len(rows), "items": [_row_to_topic(r) for r in rows]}
    finally:
        conn.close()


@app.get("/matches")
def list_matches():
    """归一后的独立场次列表（按开赛时间）。"""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT match_id, MIN(title) title, MIN(kickoff) kickoff, "
            "GROUP_CONCAT(DISTINCT bet_type) bet_types, MAX(snapshot_ts) snapshot_ts "
            "FROM topics WHERE line='单场' AND match_id IS NOT NULL "
            "GROUP BY match_id ORDER BY kickoff"
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d["title_en"] = d["title"]
            d["title"] = glossary.translate(d["title"].split(" - ")[0])
            items.append(d)
        return {"count": len(items), "items": items}
    finally:
        conn.close()


@app.get("/topic/{event_id}")
def get_topic(event_id: str):
    conn = db.connect()
    try:
        r = conn.execute("SELECT * FROM topics WHERE event_id=?", (event_id,)).fetchone()
        if not r:
            raise HTTPException(404, "选题不存在")
        return _row_to_topic(r)
    finally:
        conn.close()
