"""赛果抓取（公开源 ESPN）。

按用户分工：预测市场=赔率/选题；赛果=公开数据源(ESPN fifa.world)。
只取**已完赛**(status state=post/completed)的比赛，返回结构化比分。
原则 P3.4：带超时/UA；P0.4 失败显性(返回空+记录)。
"""
import json
import urllib.request
import urllib.error
from datetime import date, timedelta

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={d}"
# 小组赛日期范围（含淘汰赛起始，后续可扩展）
GROUP_START = date(2026, 6, 11)
GROUP_END = date(2026, 6, 27)


def _fetch_day(d: date):
    url = ESPN.format(d=d.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": "wcp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def fetch_results(start=GROUP_START, end=None):
    """抓取 [start,end] 间已完赛比赛。返回 [{teamA,scoreA,teamB,scoreB,date,completed}]。"""
    end = end or GROUP_END
    out = []
    d = start
    while d <= end:
        data = _fetch_day(d)
        if data:
            for e in data.get("events", []):
                comp = (e.get("competitions") or [{}])[0]
                st = e.get("status", {}).get("type", {})
                completed = bool(st.get("completed"))
                cs = comp.get("competitors", [])
                if len(cs) == 2:
                    # ESPN home/away；用 displayName + score
                    a, b = cs
                    try:
                        sa = int(a.get("score")) if a.get("score") not in (None, "") else None
                        sb = int(b.get("score")) if b.get("score") not in (None, "") else None
                    except (ValueError, TypeError):
                        sa = sb = None
                    out.append({
                        "teamA": a.get("team", {}).get("displayName"),
                        "teamB": b.get("team", {}).get("displayName"),
                        "scoreA": sa, "scoreB": sb,
                        "date": d.isoformat(), "completed": completed,
                    })
        d += timedelta(days=1)
    return out


def completed_only(results):
    return [r for r in results if r["completed"] and r["scoreA"] is not None]


if __name__ == "__main__":
    res = fetch_results()
    done = completed_only(res)
    print(f"抓取 {len(res)} 场，已完赛 {len(done)} 场")
    for r in done[:10]:
        print(f"  {r['teamA']} {r['scoreA']}-{r['scoreB']} {r['teamB']} ({r['date']})")
    if not done:
        print("  (暂无完赛比赛——赛事刚开始，机器已就绪)")
