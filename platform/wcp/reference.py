"""参考数据：策略说明（用户要求#4）+ 世界杯赛程进度（用户要求#3）。

策略定义同步自 3_策略分析库/核心策略清单.md 与 1_想法库/核心机会框架.md。
赛程为 2026 美加墨世界杯官方阶段时间。
"""
from datetime import date, datetime

# ---- 策略说明（卡片 tooltip + 策略页用）----
STRATEGIES = {
    "A": {"name": "强打弱·大分", "desc": "S/A级强队对C/D级鱼腩，实力差≥2档且强队有进攻动力，押全场大分（Over 2.5/3.5）或强队让球 -1.5。"},
    "B": {"name": "强队确定性", "desc": "押强队晋级到其「地板」阶段——法国进R16、葡萄牙出线这类「应该发生」的事。赔率低但稳，盈亏比1.05–1.3x。"},
    "C": {"name": "摇摆末轮生死战", "desc": "小组末轮，两队出线形势未定。按积分场景押：双方需赢→大分；平局双出→小分/平局；单队有动力→押该队胜。赛前不预设，按真实积分动态触发。"},
    "D": {"name": "比赛中观测", "desc": "据半场数据（比分/控球/射门/射正）输出对应盘口。半场0-0但控球压制明显→押下半场进球；角球密集→押角球盘。不抢市场反应，依据已发生的场上事实。"},
    "F": {"name": "准确比分博高赔", "desc": "S级打D级，小仓博具体比分。3-0约8-12x，4-0约15-20x，5-0约30-50x。一次命中覆盖多次未中，仓位用户自定。"},
    "G": {"name": "东道主效应", "desc": "美/加/墨在本土城市主场作战，主场加成约等于额外0.3-0.5球优势。重点：美国vs弱队、墨西哥vs B级队。"},
    "I": {"name": "保守踢法小分", "desc": "一队已锁定头名、一队已出局放松心态、或双方都接受平局。押全场小分（Under 2.5）、平局、下半场小分。需赛中确认状态，赛前不预设。"},
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
