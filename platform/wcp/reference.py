"""参考数据：策略说明（用户要求#4）+ 世界杯赛程进度（用户要求#3）。

策略定义同步自 3_策略分析库/核心策略清单.md 与 1_想法库/核心机会框架.md。
赛程为 2026 美加墨世界杯官方阶段时间。
"""
from datetime import date, datetime

# ---- 策略说明（卡片 tooltip + 策略页用）----
STRATEGIES = {
    "A": {"name": "强打弱·进球大分", "desc": "强队对鱼腩，押全场进球大分（O/U）。实力差≥2档、强队有动力时价值最高。"},
    "B": {"name": "强队晋级确定性", "desc": "顶级强队晋级/夺冠的确定性被市场低估时押注，赔率仍有折扣即进。"},
    "C": {"name": "摇摆队末场生死战", "desc": "小组末轮决定命运的队伍，按出线情景押大分/小分/特定队胜。"},
    "D": {"name": "盘中事件驱动", "desc": "红牌/早进球/扑点/补时等事件后赔率剧烈波动的短暂错价窗口。"},
    "E": {"name": "冷门信息差", "desc": "低关注队伍/选题，凭主力伤病等未被市场定价的信息提前布局。"},
    "F": {"name": "准确比分博高赔", "desc": "强队打鱼腩，小仓位押准确比分（3-0/4-0等），盈亏比8-15x。"},
    "G": {"name": "东道主效应", "desc": "美/加/墨主场作战，主场优势常被低估，押东道主或让球加成。"},
    "H": {"name": "疲劳差套利", "desc": "两队休息天数不等时，押体能更充沛的一方，重点关注后半段。"},
    "I": {"name": "保守踢法小分", "desc": "已出线轮换/已出局放松的比赛，押全场小分或平局。"},
    "N": {"name": "新上线先发布局", "desc": "新挂出的预测选题尚未被定价，赶在流动性涌入前以最优价建仓。"},
}

# ---- 2026 世界杯赛程阶段（官方）----
STAGES = [
    {"key": "group", "name": "小组赛", "start": "2026-06-11", "end": "2026-06-27",
     "desc": "12组每组4队，共72场。每组前2名 + 成绩最好的8个第三名晋级，共32队出线。"},
    {"key": "r32", "name": "32强淘汰赛", "start": "2026-06-28", "end": "2026-07-03",
     "desc": "单场淘汰，48队扩军后新增的一轮。"},
    {"key": "r16", "name": "16强", "start": "2026-07-04", "end": "2026-07-07", "desc": "八分之一决赛。"},
    {"key": "qf", "name": "8强", "start": "2026-07-09", "end": "2026-07-11", "desc": "四分之一决赛。"},
    {"key": "sf", "name": "4强", "start": "2026-07-14", "end": "2026-07-15", "desc": "半决赛。"},
    {"key": "third", "name": "三四名决赛", "start": "2026-07-18", "end": "2026-07-18", "desc": "季军争夺战。"},
    {"key": "final", "name": "决赛", "start": "2026-07-19", "end": "2026-07-19",
     "desc": "纽约/新泽西 MetLife 球场。"},
]


def progress(today: str | None = None):
    """返回各阶段状态：已结束/进行中/未开始 + 整体进度。"""
    d = date.fromisoformat(today) if today else date.today()
    out = []
    for s in STAGES:
        st, en = date.fromisoformat(s["start"]), date.fromisoformat(s["end"])
        if d > en:
            status = "已结束"
        elif d < st:
            status = "未开始"
        else:
            status = "进行中"
        out.append({**s, "status": status})
    # 整体进度（按时间轴）
    total_start = date.fromisoformat(STAGES[0]["start"])
    total_end = date.fromisoformat(STAGES[-1]["end"])
    span = (total_end - total_start).days or 1
    elapsed = max(0, min(span, (d - total_start).days))
    return {
        "today": d.isoformat(),
        "overall_percent": round(100 * elapsed / span),
        "current_stage": next((s["name"] for s in out if s["status"] == "进行中"),
                              "未开赛" if d < total_start else "已闭幕"),
        "stages": out,
    }
