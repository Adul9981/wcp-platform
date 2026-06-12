"""文案系统（系统2）—— 从实时数据自动生成可发布文案。

数据源：三榜(boards) + 下注方向 + 预测命中率(review) + 赛果。
对齐 5_工具建设库/文案系统.md 规范与禁忌：
  - 给明确方向 + 当前概率，不模糊
  - 禁"稳赚/必中"等误导词；附风险提示
  - 不构成投资建议
诚实：只用真实抓取的数据，方向来自已验证策略，价格一并给出。
"""
from datetime import datetime, timezone

from . import db, boards, review

DISCLAIMER = "⚠️ 仅供研究参考，不构成投资建议；预测有不确定性，请独立判断。"


def _pct(p):
    return f"{p*100:.0f}%" if p is not None else "—"


def _dir_line(e):
    d = e.get("direction")
    if not d:
        return None
    pr = f"（市场隐含 {_pct(d.get('price'))}）" if d.get("price") is not None else ""
    return f"{d['label']}{pr} · 信心{d.get('confidence','-')}"


def daily_overview(conn=None):
    """每日总览帖：三榜各取一条有方向的代表。"""
    b = boards.generate(conn, top_n=15)
    today = datetime.now(timezone.utc).strftime("%m月%d日")
    lines = [f"📅 世界杯今日预测速览（{today}）", ""]

    def pick(key):
        for e in b[key]:
            if e.get("direction"):
                return e
        return b[key][0] if b[key] else None

    blocks = [("📅 今日关注", "today"), ("🛡️ 低风险", "low_risk"), ("🎲 高风险", "high_risk")]
    for label, key in blocks:
        e = pick(key)
        if not e:
            continue
        lines.append(f"{label}：{e['title']}")
        dl = _dir_line(e)
        if dl:
            lines.append(f"  方向 → {dl}")
        if e.get("reason"):
            lines.append(f"  依据：{e['reason'][:60]}")
        lines.append("")
    lines.append(DISCLAIMER)
    lines.append("#世界杯2026 #预测")
    return "\n".join(lines)


def pre_match(conn=None):
    """赛前预测帖：取最值得关注里有方向的前3场单场。"""
    b = boards.generate(conn, top_n=20)
    picks = [e for e in b["today"] if e["line"] == "单场" and e.get("direction")][:3]
    if not picks:
        return None
    lines = ["⚽ 赛前预测 · 今日精选", ""]
    for e in picks:
        lines.append(f"【{e['title']}】")
        lines.append(f"  {_dir_line(e)}")
        tags = "·".join(e.get("strategy_tags", []))
        if tags:
            lines.append(f"  命中策略：{tags}")
        ko = e.get("kickoff")
        if ko:
            lines.append(f"  开赛：{ko[:16].replace('T',' ')}")
        lines.append("")
    lines.append(DISCLAIMER)
    lines.append("#世界杯2026 #足球预测")
    return "\n".join(lines)


def post_review(conn=None):
    """赛后复盘帖：基于预测命中率 + 最近结算。真实记录，不挑好看的。"""
    own = conn is None
    conn = conn or db.connect()
    try:
        hr = review.hit_rate(conn)
        o = hr["overall"]
        if o["样本"] == 0:
            txt = ("📊 复盘 · 赛事进行中\n\n暂无已结算预测（比赛尚未产生结果）。\n"
                   "预测已记录在册，赛后将如实公布命中与否——输赢都公开。\n\n" + DISCLAIMER)
        else:
            lines = ["📊 世界杯预测复盘", "",
                     f"累计命中：{o['命中']}/{o['样本']}（命中率 {o['命中率']}%）", ""]
            if hr["by_strategy"]:
                lines.append("分策略表现：")
                for k, v in hr["by_strategy"].items():
                    if v["样本"]:
                        lines.append(f"  策略{k}：{v['命中']}/{v['样本']}（{v['命中率']}%）")
                lines.append("")
            lines.append("真实记录，输赢都公开。")
            lines.append(DISCLAIMER)
            txt = "\n".join(lines)
        return txt
    finally:
        if own:
            conn.close()


def generate_all(conn=None):
    own = conn is None
    conn = conn or db.connect()
    try:
        out = []
        out.append({"type": "每日总览", "text": daily_overview(conn)})
        pm = pre_match(conn)
        if pm:
            out.append({"type": "赛前预测", "text": pm})
        out.append({"type": "赛后复盘", "text": post_review(conn)})
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    for piece in generate_all():
        print("=" * 50)
        print(f"【{piece['type']}】\n")
        print(piece["text"])
        print()
