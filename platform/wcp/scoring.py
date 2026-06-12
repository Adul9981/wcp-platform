"""三榜评分 —— 全部可解释（原则 P2.1：不做黑箱）。

诚实声明（原则 P0.1 / P2.2）：
当前未接入外部博彩赔率，**不计算"公平价值/edge"，也不臆造**。
新三榜（今日关注/低风险/高风险）基于：策略匹配、时间（今日）、风险分类（实力×阶段）、盈亏比。
"""
import math
from datetime import datetime, timezone


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm_log(x, hi):
    """对数归一到 0..1。hi 为参考上界。"""
    if not x or x <= 0:
        return 0.0
    return min(1.0, math.log10(1 + x) / math.log10(1 + hi))


def payoff_ratio(price):
    """盈亏比 ≈ 1/隐含概率（赢1注的毛回报倍数）。"""
    if not price or price <= 0:
        return None
    return round(1.0 / price, 2)


def score_attention(t):
    """🎯 最值得关注：策略匹配 × 流动性(可成交) × 成交活跃。"""
    strat = min(1.0, len(t["strategy_tags"]) / 4.0)
    liq = _norm_log(t["liquidity"], 1_000_000)
    vol = _norm_log(t["volume"], 10_000_000)
    score = 0.40 * strat + 0.35 * liq + 0.25 * vol
    reason = f"命中{len(t['strategy_tags'])}条策略{t['strategy_tags']}；" \
             f"流动性{t['liquidity']:.0f}；成交{t['volume']:.0f}"
    return round(score, 4), reason


def score_overlooked(t):
    """💎 最被忽视·低关注：有策略逻辑 + 低关注度/新上线（低流动属正常，不剔除）。

    原则：**低流动性不作为剔除理由**。
    新上线/低成交是正常状态，不设流动性门槛。
    门槛仅：必须有策略逻辑（无逻辑的冷门=噪声）+ 有有效报价。
    防刷屏靠 boards 层按场次去重，不靠流动性过滤。
    """
    if not t["strategy_tags"] or t["price"] is None:
        return 0.0, ""
    low_attention = 1.0 - _norm_log(t["volume"], 10_000_000)
    strat = min(1.0, len(t["strategy_tags"]) / 4.0)
    new_bonus = 1.0 if t["is_new"] else 0.0
    interest, ikind = _interest(t)   # 有趣度：顶出H2H/大洲/球员等深挖盘
    score = 0.35 * low_attention + 0.15 * strat + 0.10 * new_bonus + 0.40 * interest
    tag = "新上线" if t["is_new"] else "低关注"
    extra = f"·{ikind}" if ikind else ""
    reason = f"{tag}{extra}+策略{t['strategy_tags']}；成交仅{t['volume']:.0f}（低流动属正常，不剔除）"
    return round(score, 4), reason


# 深挖出的"被忽视但有趣"盘类型 → 高有趣度
_INTERESTING = {
    "球员H2H": "H2H对决", "夺冠": "", "大洲夺冠": "大洲盘", "球员参赛": "球员市场",
}
_INTERESTING_CAT = {
    "12大洲夺冠": "大洲盘", "10大洲其他": "大洲盘", "08花边政治": "花边盘",
    "13球员参赛": "球员市场", "07球员表现": "球员盘", "03个人奖项": "个人奖项",
    "02射手榜": "射手榜", "09赛事纪录": "纪录盘", "06小组排名": "小组排名", "11小组头名": "小组头名",
}
# 重复刷屏的单场衍生盘 → 低有趣度(不该霸占被忽视榜)
_BORING_BET = {"首开记录", "比分", "角球", "BTTS", "半场", "其他衍生"}


def _interest(t):
    cat = t.get("category") or ""
    bet = t.get("bet_type") or ""
    if bet in _INTERESTING:
        return 1.0, _INTERESTING[bet]
    if cat in _INTERESTING_CAT:
        return 1.0, _INTERESTING_CAT[cat]
    if bet in _BORING_BET:
        return 0.15, ""
    return 0.5, ""


# ══════════════════════════════════════════════════════
# 新三榜评分：今日关注 / 低风险 / 高风险
# ══════════════════════════════════════════════════════

def score_today(t, today: str | None = None) -> tuple[float, str]:
    """📅 今日关注：今天开赛且尚未结束（开球后 <2h）的比赛，按策略质量排序。"""
    td = today or _today_str()
    kickoff = t.get("kickoff") or ""
    if not kickoff.startswith(td):
        return 0.0, ""
    # 比赛开始超过 2 小时视为已结束，不再展示
    try:
        ko_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - ko_dt).total_seconds() > 7200:
            return 0.0, ""
    except (ValueError, TypeError):
        pass
    tags = t.get("strategy_tags") or []
    strat = min(1.0, len(tags) / 3.0)
    score = 0.50 + 0.50 * strat
    reason = f"今日开赛·策略 {'·'.join(tags) if tags else '无'}"
    return round(score, 4), reason


def score_low_risk(t) -> tuple[float, str]:
    """🛡️ 低风险：主张 ≤ 队伍地板（强队确定性/东道主/已出线保守）。
    入选条件：有 B/G/I 策略，或 A 策略且实力差 ≥ 3 档；价格 0.50-0.92。
    """
    tags = t.get("strategy_tags") or []
    p = t.get("price")
    has_b = "B" in tags
    has_g = "G" in tags
    has_i = "I" in tags
    has_a = "A" in tags

    if not (has_b or has_g or has_i or has_a):
        return 0.0, ""
    if p is None or p < 0.50 or p > 0.92:
        return 0.0, ""

    strat_score, parts = 0.0, []
    if has_b:
        strat_score += 0.7; parts.append("强队确定性(B)")
    if has_g:
        strat_score += 0.4; parts.append("东道主(G)")
    if has_i:
        strat_score += 0.3; parts.append("小分保守(I)")
    if has_a and not has_b:
        strat_score += 0.4; parts.append("强打弱(A)")

    # 甜蜜区 0.65–0.85：确定但还有赔付价值
    if 0.65 <= p <= 0.85:
        price_score = 1.0
    elif p > 0.85:
        price_score = max(0.0, 1.0 - (p - 0.85) / 0.07)
    else:
        price_score = (p - 0.50) / 0.15

    score = 0.60 * min(1.0, strat_score) + 0.40 * price_score
    pr = payoff_ratio(p)
    reason = f"低风险·{'·'.join(parts)}；盈亏比≈{pr}x（隐含{p*100:.0f}%）"
    return round(score, 4), reason


def score_high_risk(t) -> tuple[float, str]:
    """🎲 高风险：长赔子区（price<0.30）或 摇摆子区（C/势均力敌，0.30-0.70）。"""
    tags = t.get("strategy_tags") or []
    p = t.get("price")
    if not tags or p is None or p <= 0:
        return 0.0, ""
    pr = payoff_ratio(p)

    # 长赔子区：price<0.30 + 有策略支撑
    if p < 0.30:
        pr_score = min(1.0, math.log10(max(pr, 1.01)) / math.log10(50))
        score = 0.70 * pr_score + 0.30 * min(1.0, len(tags) / 3.0)
        reason = f"长赔·盈亏比≈{pr}x（隐含{p*100:.0f}%）；策略{'·'.join(tags)}"
        return round(score + 0.05, 4), reason   # +0.05 让长赔排在摇摆之上

    # 摇摆子区：C策略 + 价格在博弈区间
    if "C" in tags and 0.30 <= p <= 0.70:
        swing = max(0.0, 1.0 - abs(p - 0.50) / 0.20)
        strat = min(1.0, len(tags) / 3.0)
        score = 0.55 * swing + 0.45 * strat
        reason = f"摇摆·末轮生死战(C)；盈亏比≈{pr}x（隐含{p*100:.0f}%）"
        return round(score, 4), reason

    # 摇摆子区（宽松）：A策略 + 价格接近博弈区
    if "A" in tags and 0.35 <= p <= 0.65:
        score = 0.40 + 0.20 * min(1.0, len(tags) / 3.0)
        reason = f"摇摆·势均力敌(A)；盈亏比≈{pr}x（隐含{p*100:.0f}%）"
        return round(score, 4), reason

    return 0.0, ""


def score_payoff(t):
    """📈 最大盈亏比：低隐含概率(高赔率) + 有逻辑支撑 + 最低可成交流动性。"""
    p = t["price"]
    if not p or p <= 0:
        return 0.0, ""
    # 门槛：过滤接近必然(>0.5)与尘埃盘(<0.02)；需有策略支撑
    if p > 0.5 or p < 0.02 or not t["strategy_tags"]:
        return 0.0, ""
    pr = payoff_ratio(p)
    # 盈亏比贡献（对数压缩，避免极端尘埃盘霸榜）+ 流动性可成交性
    pr_score = min(1.0, math.log10(pr) / math.log10(50))  # 50x 封顶
    liq = _norm_log(t["liquidity"], 1_000_000)
    score = 0.70 * pr_score + 0.30 * liq
    reason = f"盈亏比≈{pr}x（隐含{p*100:.1f}%）+ 逻辑{t['strategy_tags']}；流动性{t['liquidity']:.0f}"
    return round(score, 4), reason
