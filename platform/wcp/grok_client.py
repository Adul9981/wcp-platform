"""xAI Grok API 客户端 —— 赛程获取、赛前预测生成、赛后多源结果确认。

API key 通过环境变量 XAI_API_KEY 注入，禁止硬编码。
"""
import os
import json
import requests
from datetime import datetime, timezone

XAI_BASE = "https://api.x.ai/v1"
WC_2026_START = datetime(2026, 6, 11, tzinfo=timezone.utc)


def _model() -> str:
    return os.environ.get("XAI_MODEL", "grok-2-latest")


def tournament_day(dt: datetime | None = None) -> int:
    """世界杯第N天，从2026-06-11（Day1）起算。"""
    d = dt or datetime.now(timezone.utc)
    return max(1, (d - WC_2026_START).days + 1)


def _chat(messages: list, search: bool = True, temperature: float = 0.3) -> str:
    key = os.environ.get("XAI_API_KEY", "")
    if not key:
        raise RuntimeError("XAI_API_KEY 未配置，请在 Railway 环境变量中设置")
    payload = {
        "model": _model(),
        "messages": messages,
        "temperature": temperature,
    }
    if search:
        payload["search_parameters"] = {
            "mode": "auto",
            "sources": [{"type": "web"}, {"type": "x"}],
        }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"{XAI_BASE}/chat/completions", headers=headers,
                          json=payload, timeout=120)
        r.raise_for_status()
    except requests.HTTPError as e:
        # 如果模型不支持 search_parameters，退回无搜索重试
        if search and hasattr(e, "response") and e.response is not None and e.response.status_code in (422, 400):
            payload.pop("search_parameters", None)
            r = requests.post(f"{XAI_BASE}/chat/completions", headers=headers,
                              json=payload, timeout=120)
            r.raise_for_status()
        else:
            raise
    return r.json()["choices"][0]["message"]["content"]


def _parse_json(text: str):
    """从可能含 markdown 代码块的响应中提取 JSON。"""
    text = text.strip()
    if "```" in text:
        for part in text.split("```")[1::2]:
            s = part.strip()
            if s.startswith("json"):
                s = s[4:].strip()
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                continue
    return json.loads(text)


# ──────────────────────────────────────────────
# 1. 今日赛程
# ──────────────────────────────────────────────

def get_todays_matches(date_str: str) -> list[dict]:
    """让 Grok 搜索并返回今天的世界杯赛程。"""
    prompt = (
        f"今天是 {date_str}（UTC），2026年FIFA世界杯进行中。\n\n"
        f"请搜索今天（{date_str}）所有世界杯比赛安排，以 JSON 数组返回：\n"
        '[{"home":"主队中文名","away":"客队中文名","kickoff_utc":"YYYY-MM-DDTHH:MM:00Z","stage":"小组赛X组第Y轮或淘汰赛阶段"}]\n\n'
        "如今天没有比赛，返回 []。只返回 JSON，不加任何额外说明。"
    )
    text = _chat([{"role": "user", "content": prompt}], search=True)
    return _parse_json(text)


# ──────────────────────────────────────────────
# 2. 赛前预测生成
# ──────────────────────────────────────────────

_PRED_PROMPT = """\
你是专业世界杯预测分析师。今天是{date_str}，2026年FIFA世界杯。

今日比赛：
{match_list}

请搜索每场比赛的最新资讯（伤病停赛、近期状态、积分出线形势、当前赔率），\
然后严格按以下格式输出，不要添加任何额外前言或结尾：

Day{day}赛前预测

{match_blocks}
"""

_MATCH_BLOCK = """\
{num}. {home} vs {away}
推理：
[2-3句精准分析：关键球员伤病、近期状态、赛事阶段压力，有具体数字和事实]

预测：[明确结论]。比分倾向[X-Y]或[X-Y]。
主推：[押注选项]（回报率约[XX-XX]%）
备选：[选项2]
       [选项3（如有）]"""


def generate_predictions(matches: list[dict], date_str: str) -> str:
    """生成格式化赛前预测文本。"""
    day = tournament_day()
    match_list = "\n".join(
        f"{i+1}. {m['home']} vs {m['away']}（{m.get('stage','')}，{m.get('kickoff_utc','待定')} UTC）"
        for i, m in enumerate(matches)
    )
    blocks = "\n\n".join(
        _MATCH_BLOCK.format(num=i+1, home=m["home"], away=m["away"])
        for i, m in enumerate(matches)
    )
    prompt = _PRED_PROMPT.format(date_str=date_str, day=day,
                                  match_list=match_list, match_blocks=blocks)
    return _chat([{"role": "user", "content": prompt}], search=True, temperature=0.5)


# ──────────────────────────────────────────────
# 3. 赛后结果确认
# ──────────────────────────────────────────────

def get_match_results(matches: list[dict], date_str: str) -> list[dict]:
    """从多个来源确认比赛最终比分。"""
    match_list = "\n".join(f"- {m['home']} vs {m['away']}" for m in matches)
    prompt = (
        f"2026年FIFA世界杯，{date_str}的以下比赛已经结束，"
        "请从多个来源（ESPN、FIFA官网、BBC Sport、Soccerway等）交叉确认最终比分：\n\n"
        f"{match_list}\n\n"
        "以 JSON 数组返回：\n"
        '[{"home":"主队","away":"客队","home_score":0,"away_score":0,'
        '"winner":"主队/客队/平局","confirmed":true,"note":"加时/点球等说明，无则空字符串"}]\n\n'
        "只返回 JSON，不加任何额外说明。"
    )
    text = _chat([{"role": "user", "content": prompt}], search=True)
    return _parse_json(text)


# ──────────────────────────────────────────────
# 4. 预测评估（对比预测与结果）
# ──────────────────────────────────────────────

def evaluate_predictions(pred_content: str, results: list[dict]) -> str:
    """让 Grok 对比预测与实际结果，生成结果评估文本。"""
    day = tournament_day() - 1
    results_str = "\n".join(
        f"- {r['home']} vs {r['away']}: {r.get('home_score','?')}-{r.get('away_score','?')}"
        f"，{r.get('winner','?')}{('，'+r['note']) if r.get('note') else ''}"
        for r in results
    )
    prompt = (
        f"以下是赛前预测内容：\n\n{pred_content}\n\n"
        f"实际比赛结果：\n{results_str}\n\n"
        "请严格对比预测与结果，按以下格式输出（只输出这部分，不加其他内容）：\n\n"
        f"Day{day}预测结果：\n"
        "[主队] vs [客队]\n"
        "主推：[我们预测的主推] ✅/❌（实际 X-Y，[一句关键点评]）\n"
        "备选：[我们预测的备选] ✅/❌（如有）\n\n"
        "（对每场比赛重复，编号递增）\n\n"
        "判断规则：胜平负方向正确=✅，错误=❌，0️⃣=无法判断/弃权"
    )
    return _chat([{"role": "user", "content": prompt}], search=False, temperature=0.2)
