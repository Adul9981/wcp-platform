"""M1 数据管道编排：抓取 → 归一/去重 → 打标 → 标新 → 落库。

运行: python -m wcp.pipeline
"""
from . import config, db, direction, results as results_mod, standings, review
from .client import PolymarketClient
from .normalize import build_topics


def run(verbose=True):
    cli = PolymarketClient()

    if verbose:
        print("[1/5] 抓取长盘 tag", config.TAG_WORLD_CUP, "...")
    long_events = cli.get_all_events(tag_id=config.TAG_WORLD_CUP, active=True, closed=False)

    if verbose:
        print(f"      长盘 {len(long_events)} 个")
        print("[2/5] 抓取单场盘 series", config.SERIES_MATCHES, "...")
    match_events = cli.get_all_events(series_id=config.SERIES_MATCHES, active=True, closed=False)
    if verbose:
        print(f"      单场盘 event {len(match_events)} 个")

    # 动态数据闭环：抓赛果→更新积分/出线状态(供策略B/C/I使用)
    if verbose:
        print("[2.5/5] 抓赛果 + 更新小组积分/出线形势 ...")
    done = []
    try:
        done = results_mod.completed_only(results_mod.fetch_results())
        dyn_summary = standings.update_teams(done)
    except Exception as e:
        dyn_summary = {"error": f"{type(e).__name__}: {e}", "results_used": 0}
    if verbose:
        print(f"      完赛 {dyn_summary.get('results_used',0)} 场，更新 {dyn_summary.get('teams_updated',0)} 队")

    if verbose:
        print("[3/5] 归一 + 去重 + 打标 + 下注方向 ...")
    topics, stats = build_topics(long_events, match_events)
    stats["dynamic"] = dyn_summary
    direction.annotate(topics)

    conn = db.connect()
    db.init_db(conn)
    if verbose:
        print("[4/5] 检测新上线(先发机会) ...")
    new_ids = db.mark_new_events(conn, topics, stats["ts"])

    if verbose:
        print("[5/5] 落库 + 复盘快照/判定 ...")
    db.upsert_topics(conn, topics)
    # 复盘A：快照单场预测 + 用赛果判定历史预测命中
    snapped = review.snapshot_predictions(conn, topics)
    settled = review.resolve_predictions(conn, done)
    if verbose:
        print(f"      预测快照 {snapped} 条，本次判定 {settled} 条")
    conn.close()

    result = {
        **stats,
        "total_topics": len(topics),
        "new_events": len(new_ids),
    }
    if verbose:
        print("---- 完成 ----")
        print(f"  长盘选题:        {stats['long_count']}")
        print(f"  单场 event:      {stats['match_event_count']}")
        print(f"  归一独立场次:     {stats['distinct_matches']}")
        print(f"  总选题入库:       {result['total_topics']}")
        print(f"  本次新上线:       {result['new_events']}")
        print(f"  快照时间:         {stats['ts']}")
    return result


if __name__ == "__main__":
    run()
