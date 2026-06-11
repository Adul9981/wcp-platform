"""集中配置 —— 受平台建设原则 P3/P6 约束：配置与密钥分离，邀请码集中管理、禁硬编码。

实际部署时敏感值走环境变量；本文件提供默认值与单一真相来源。
"""
import os

# ---- Polymarket API (只读端点，无需认证) ----
GAMMA_BASE = os.getenv("WCP_GAMMA_BASE", "https://gamma-api.polymarket.com")
CLOB_BASE = os.getenv("WCP_CLOB_BASE", "https://clob.polymarket.com")
DATA_BASE = os.getenv("WCP_DATA_BASE", "https://data-api.polymarket.com")

# 世界杯数据源入口（见 2_数据库/预测市场接入.md 核查结论）
# 102232 "FIFA World Cup" = umbrella 超集(619事件)，含小组头名/大洲/球员期货等子分类，
# 取代旧的窄 tag 102350(仅152、漏小组头名/大洲/球员盘)。深挖发现，2026-06-11。
TAG_WORLD_CUP = os.getenv("WCP_TAG", "102232")        # FIFA World Cup 全量专题
SERIES_MATCHES = os.getenv("WCP_SERIES", "11433")     # 单场比赛盘 (fifwc)

# 数据自动刷新间隔(分钟)。P3.5 尊重数据源：默认30min，赛中可调小。
REFRESH_INTERVAL_MIN = int(os.getenv("WCP_REFRESH_MIN", "30"))

# ---- HTTP 行为 (原则 P3.4：带超时/退避重试/UA；urllib直连会403，必须带UA) ----
USER_AGENT = os.getenv("WCP_UA", "wcp-platform/0.1 (+worldcup-predictor)")
HTTP_TIMEOUT = int(os.getenv("WCP_TIMEOUT", "30"))
HTTP_RETRIES = int(os.getenv("WCP_RETRIES", "4"))
HTTP_BACKOFF = float(os.getenv("WCP_BACKOFF", "1.5"))  # 退避基数(秒)
PAGE_LIMIT = 100   # Gamma API 单页硬上限，limit>100 无效，必须翻页

# ---- 邀请码 (原则 P6：集中管理、禁硬编码) ----
# 参数名 + 值，整体可配；当前用户提供：?via=serene77mc-g6kj
POLYMARKET_REFERRAL_PARAM = os.getenv("WCP_REFERRAL_PARAM", "via")
POLYMARKET_REFERRAL_CODE = os.getenv("WCP_REFERRAL", "serene77mc-g6kj")


def build_event_url(slug: str) -> str:
    """生成带推荐归因的 Polymarket 选题跳转链接。全站唯一入口。

    模板: https://polymarket.com/event/{slug}?{param}={code}
    (#fragment 不发往服务端、归因不依赖，故省略)
    """
    if not slug:
        return ""
    return (f"https://polymarket.com/event/{slug}"
            f"?{POLYMARKET_REFERRAL_PARAM}={POLYMARKET_REFERRAL_CODE}")


# ---- 存储 ----
DB_PATH = os.getenv("WCP_DB", os.path.join(os.path.dirname(__file__), "..", "data", "wcp.db"))
