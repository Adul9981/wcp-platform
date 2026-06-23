"""自动预测流程编排 —— 早间生成预测，赛后更新结果。

两个入口：
  run_morning_job()  —— 获取赛程 → Grok分析 → 自动发布
  run_results_job()  —— 多源确认结果 → 评估预测 → 更新记录
"""
import json
import logging
from datetime import datetime, timezone
from . import db, grok_client

log = logging.getLogger(__name__)


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_todays_auto_pred(conn, date_str: str):
    return conn.execute(
        "SELECT * FROM predictions WHERE is_auto=1 AND created_ts >= ?"
        " ORDER BY id DESC LIMIT 1",
        (date_str,)
    ).fetchone()


def run_morning_job(date_str: str | None = None) -> dict:
    """
    早间任务：
    1. 让 Grok 搜索今日赛程
    2. 让 Grok 生成格式化赛前预测
    3. 写入/更新 predictions 表并发布
    """
    today = date_str or _today_str()
    log.info("[auto_predict] morning job → %s", today)

    matches = grok_client.get_todays_matches(today)
    if not matches:
        log.info("[auto_predict] no matches today")
        return {"ok": True, "status": "no_matches", "date": today}

    content = grok_client.generate_predictions(matches, today)
    day = grok_client.tournament_day()
    ts = datetime.now(timezone.utc).isoformat()

    conn = db.connect()
    try:
        existing = _get_todays_auto_pred(conn, today)
        if existing:
            conn.execute(
                "UPDATE predictions SET content=?, matches_json=?, day_num=?, updated_ts=? WHERE id=?",
                (content, json.dumps(matches, ensure_ascii=False), day, ts, existing["id"])
            )
            pid = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO predictions"
                "(match_name,kickoff,content,status,published,is_auto,day_num,matches_json,created_ts,updated_ts)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (f"Day{day} 赛前预测",
                 matches[0].get("kickoff_utc"),
                 content, "active", 1, 1, day,
                 json.dumps(matches, ensure_ascii=False),
                 ts, ts)
            )
            pid = cur.lastrowid
        conn.commit()
        log.info("[auto_predict] morning done → id=%s matches=%d", pid, len(matches))
        return {"ok": True, "status": "published", "id": pid,
                "matches": len(matches), "date": today}
    finally:
        conn.close()


def run_results_job(date_str: str | None = None) -> dict:
    """
    赛后任务：
    1. 读取今天的自动预测记录（含赛程JSON）
    2. 让 Grok 多源确认比赛结果
    3. 让 Grok 对比预测与结果
    4. 将评估文本写回 result_text 字段
    """
    today = date_str or _today_str()
    log.info("[auto_predict] results job → %s", today)

    conn = db.connect()
    try:
        pred = _get_todays_auto_pred(conn, today)
        if not pred:
            log.warning("[auto_predict] no auto pred found for %s", today)
            return {"ok": False, "status": "no_pred_found", "date": today}

        pred_dict = dict(pred)
        raw_json = pred_dict.get("matches_json")
        if not raw_json:
            return {"ok": False, "status": "no_matches_json"}

        matches = json.loads(raw_json)
        results = grok_client.get_match_results(matches, today)
        result_text = grok_client.evaluate_predictions(pred_dict["content"], results)

        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE predictions SET result_text=?, updated_ts=? WHERE id=?",
            (result_text, ts, pred_dict["id"])
        )
        conn.commit()
        log.info("[auto_predict] results done → id=%s results=%d", pred_dict["id"], len(results))
        return {"ok": True, "status": "updated", "id": pred_dict["id"],
                "results": len(results), "date": today}
    finally:
        conn.close()
