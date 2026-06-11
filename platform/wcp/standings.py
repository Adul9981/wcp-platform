"""小组积分与出线形势计算 + 回写 teams.json 动态区。

48队赛制：每组4队循环，每组前2 + 成绩最好的8个第三名 → 共32队出线。
据此更新每队 dynamic：played/w/d/l/gf/ga/pts/group_rank/status。
status: 未开赛 / 小组赛中 / 已出线 / 已淘汰 / 待定。
解锁策略 B(强队晋级确定性)/C(摇摆队末场)/I(保守踢法)。
"""
import json
import os
from datetime import datetime, timezone

from . import teams as teams_mod

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "teams.json")


def _blank():
    return {"played": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0}


def compute(results):
    """results: completed_only 输出。返回 {team_en: stat}（team_en 为 teams.json key）。"""
    stats = {}
    for r in results:
        ta = teams_mod.get(r["teamA"])
        tb = teams_mod.get(r["teamB"])
        if not ta or not tb:
            continue            # 不在48队名单（理论不会），跳过
        ka, kb = ta["name_en"], tb["name_en"]
        sa, sb = r["scoreA"], r["scoreB"]
        for k in (ka, kb):
            stats.setdefault(k, _blank())
        stats[ka]["played"] += 1
        stats[kb]["played"] += 1
        stats[ka]["gf"] += sa; stats[ka]["ga"] += sb
        stats[kb]["gf"] += sb; stats[kb]["ga"] += sa
        if sa > sb:
            stats[ka]["w"] += 1; stats[ka]["pts"] += 3; stats[kb]["l"] += 1
        elif sa < sb:
            stats[kb]["w"] += 1; stats[kb]["pts"] += 3; stats[ka]["l"] += 1
        else:
            stats[ka]["d"] += 1; stats[kb]["d"] += 1
            stats[ka]["pts"] += 1; stats[kb]["pts"] += 1
    return stats


def _rank_group(group_teams, stats):
    """组内排序：积分→净胜球→进球。返回有序 [(team_en, stat)]。"""
    def key(t):
        s = stats.get(t["name_en"], _blank())
        return (s["pts"], s["gf"] - s["ga"], s["gf"])
    return sorted(group_teams, key=key, reverse=True)


def _status(rank, played, pts, gd, third_cutoff_pts):
    """据排名/轮次判定状态。3轮制：rank1-2基本出线；rank3看是否达第三名门槛。"""
    if played == 0:
        return "未开赛"
    if played < 3:
        return "小组赛中"
    # 三场踢完
    if rank <= 2:
        return "已出线"
    if rank == 3 and pts >= third_cutoff_pts:
        return "已出线"  # 较好第三名（近似，精确需跨组比较）
    return "已淘汰"


def update_teams(results, write=True):
    """根据赛果回写 teams.json 动态区。返回更新摘要。"""
    with open(_PATH, encoding="utf-8") as f:
        data = json.load(f)
    teams = data["teams"]
    stats = compute(results)

    # 按组聚合并排名
    groups = {}
    for en, t in teams.items():
        groups.setdefault(t["group"], []).append(t)

    # 估算第三名出线门槛（所有打满3场的第三名里，第8好的积分）—— 近似
    third_pts = []
    for g, ts in groups.items():
        ranked = _rank_group(ts, stats)
        if len(ranked) >= 3:
            s3 = stats.get(ranked[2]["name_en"], _blank())
            if s3["played"] >= 3:
                third_pts.append(s3["pts"])
    third_pts.sort(reverse=True)
    cutoff = third_pts[7] if len(third_pts) >= 8 else 0

    ts_now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for g, ts in groups.items():
        ranked = _rank_group(ts, stats)
        for i, t in enumerate(ranked, 1):
            s = stats.get(t["name_en"], _blank())
            dyn = t["dynamic"]
            dyn.update(s)
            dyn["group_rank"] = i if s["played"] > 0 else None
            dyn["status"] = _status(i, s["played"], s["pts"], s["gf"] - s["ga"], cutoff)
            dyn["last_updated"] = ts_now
            if s["played"] > 0:
                updated += 1

    if write:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    teams_mod._load.cache_clear()  # 失效缓存，让后续读到新动态
    return {"results_used": len(results), "teams_updated": updated, "third_cutoff_pts": cutoff}


if __name__ == "__main__":
    from . import results as R
    done = R.completed_only(R.fetch_results())
    summary = update_teams(done)
    print("动态更新:", summary)
    if not done:
        print("（暂无完赛——动态区保持未开赛，机器已就绪）")
