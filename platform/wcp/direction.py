"""下注方向推荐（P3）。

诚实边界（原则 P2.2 不夸大）：
方向 = "策略的方向性主张" + 当前市场价格，供用户自行判断价值。
我们**未接外部公平赔率**，不声称算出了稳赢 edge。价格(隐含概率)一并给出，用户自己看值不值。
不满足任何已验证策略 → 不给方向（宁缺毋滥，不硬凑）。

返回结构 direction:
  {
    "label":   "押 墨西哥 胜",        # 给用户看的中文方向
    "outcome": "Mexico",             # 对应 Polymarket 选项
    "price":    0.695,               # 该选项当前隐含概率
    "basis":   "策略A 强打弱：分级差3档，强队墨西哥",  # 依据(可解释)
    "confidence": "中",              # 高/中/低，由策略类型+价格区间定性
  }
"""
from . import teams, players

_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _strong_team(a, b):
    ta, tb = teams.tier(a), teams.tier(b)
    if ta is None or tb is None:
        return None
    return a if _ORDER[ta] <= _ORDER[tb] else b


def _find_outcome(outcomes, predicate):
    """在 outcomes 里找第一个 name 命中 predicate 的项。"""
    for o in outcomes or []:
        if predicate((o.get("name") or "")):
            return o
    return None


def _conf(price):
    """价格落在合理可执行区间→信心更高；极端价格降级。"""
    if price is None:
        return "低"
    if 0.45 <= price <= 0.80:
        return "中"
    if price > 0.80:
        return "低"   # 已被充分定价，价值有限
    return "低"        # 太低=冷门，需更强理由


def recommend(topic: dict) -> dict | None:
    """给单个 topic 推荐方向。topic 为 dict（含 teams/bet_type/strategy_tags/outcomes）。"""
    tags = topic.get("strategy_tags") or []
    bet = topic.get("bet_type") or ""
    outs = topic.get("outcomes") or []
    tm = topic.get("teams") or []

    if not tags:
        return None  # 无已验证策略，不给方向

    # —— 单场 1X2：策略A→押强队胜；仅G→押东道主 ——
    if bet == "1X2" and len(tm) == 2:
        a, b = tm
        if "A" in tags:
            strong = _strong_team(a, b)
            if strong:
                o = _find_outcome(outs, lambda n: n == strong)
                price = o.get("price") if o else None
                gap = teams.tier_gap(a, b)
                return {
                    "label": f"押 {teams.get(strong)['name_zh']} 胜",
                    "outcome": strong, "price": price,
                    "basis": f"策略A 强打弱：分级差{gap}档，强队{teams.get(strong)['name_zh']}",
                    "confidence": _conf(price),
                }
        if "G" in tags:
            host = next((x for x in (a, b) if teams.is_host(x)), None)
            if host:
                o = _find_outcome(outs, lambda n: n == host)
                price = o.get("price") if o else None
                return {
                    "label": f"押 {teams.get(host)['name_zh']}（东道主）",
                    "outcome": host, "price": price,
                    "basis": f"策略G 东道主主场：{teams.get(host)['name_zh']}",
                    "confidence": _conf(price),
                }

    # —— 综合盘(含大小球) ——
    if "综合" in bet:
        o = _find_outcome(outs, lambda n: n.lower().replace(" ", "") in ("o/u2.5", "ou2.5", "over2.5"))
        over_p = o.get("price") if o else None       # P(大于2.5)
        if "I" in tags:   # 已出线轮换→小分(优先于A，出线状态是更新更具体的信息)
            under_p = round(1 - over_p, 4) if over_p is not None else None
            return {
                "label": "押 小分（Under 2.5）",
                "outcome": "Under 2.5", "price": under_p,
                "basis": "策略I 保守踢法：一方已出线，末轮或轮换→小分",
                "confidence": _conf(under_p),
            }
        if "A" in tags or "C" in tags:   # 强打弱/末轮生死战→大分
            basis = "策略C 末轮生死战：双方需进攻" if "C" in tags else "策略A 强打弱：实力悬殊，进球期望高"
            return {
                "label": "押 大分（Over 2.5）",
                "outcome": "Over 2.5", "price": over_p,
                "basis": basis,
                "confidence": _conf(over_p),
            }

    # —— 准确比分：策略F→强队大比分(文本方向，比分选项太多不锁定单一价格) ——
    if bet == "比分" and "F" in tags and len(tm) == 2:
        strong = _strong_team(tm[0], tm[1])
        if strong:
            return {
                "label": f"小仓博 {teams.get(strong)['name_zh']} 大比分(如2-0/3-0)",
                "outcome": None, "price": None,
                "basis": "策略F 准确比分：强弱悬殊，高赔率小仓博弈",
                "confidence": "低",
            }

    # —— 长盘多队盘(夺冠/晋级/出线)：每个选项=一支队，推荐我方分级最强的队 ——
    # 诚实边界：这是"分级主张"非价值edge；价格一并给出供判断。强队价格已高→信心相应降。
    if bet in ("夺冠", "晋级", "出线", "小组头名") and len(outs) >= 3:
        best = _best_team_outcome(outs)
        if best and (best["price"] is None or best["price"] <= 0.92):  # >92%无赔付价值，不推
            zh = teams.get(best["team"])["name_zh"]
            act = {"夺冠": "夺冠", "晋级": "晋级", "出线": "出线", "小组头名": "拿小组第一"}[bet]
            price = best["price"]
            return {
                "label": f"押 {zh} {act}",
                "outcome": best["team"], "price": price,
                "basis": f"策略B 强队确定性：{zh}为我方分级最高({teams.tier(best['team'])}级/FIFA{teams.get(best['team'])['fifa_rank'] or '>50'})",
                "confidence": _conf(price),
            }

    # —— 球员 H2H：用球员信息库的进球期望代理选占优者 ——
    if bet == "球员H2H":
        title = topic.get("title") or ""
        if "H2H:" in title:
            after = title.split("H2H:")[-1]
            seg = after.replace(" vs.", " vs").split(" vs")
            if len(seg) >= 2:
                a, b = seg[0].strip(), seg[1].strip(" .")
                win, basis = players.h2h_pick(a, b)
                if win:
                    pa = topic.get("price")  # = P(首名球员 a 胜)
                    price = pa if (win == a and pa is not None) else (
                        round(1 - pa, 4) if pa is not None else None)
                    # 市场强烈反对(我方所选<40%)时，粗代理不足以逆势→不推(诚实)
                    if price is not None and price < 0.40:
                        return None
                    wp = players.get(win)
                    return {
                        "label": f"押 {wp['name_zh'] if wp else win} 进球更多",
                        "outcome": win, "price": price,
                        "basis": f"H2H 对决 · {basis}",
                        "confidence": _conf(price),
                    }

    # 淘汰阶段盘(单队×各阶段)：选项语义模糊(概率和>1)，暂不给方向，避免误导。
    return None


def _best_team_outcome(outs):
    """在多队选项里挑我方分级最强的队(tier优先，其次FIFA排名)。返回 {team, price} 或 None。"""
    best = None
    for o in outs:
        t = teams.get(o.get("name") or "")
        if not t:
            continue
        key = (_ORDER[t["tier"]], t["fifa_rank"] if t["fifa_rank"] is not None else 999)
        if best is None or key < best[0]:
            best = (key, {"team": t["name_en"], "price": o.get("price")})
    return best[1] if best else None


def annotate(topics: list):
    """批量为 Topic 对象填 direction。"""
    for t in topics:
        d = {
            "title": t.title, "teams": t.teams, "bet_type": t.bet_type,
            "strategy_tags": t.strategy_tags, "outcomes": t.outcomes,
            "price": t.price,
        }
        t.direction = recommend(d)
    return topics
