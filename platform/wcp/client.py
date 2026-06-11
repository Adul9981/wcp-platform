"""Polymarket 只读抓取客户端。

原则 P1.1 读写分离：本模块仅读，绝不涉及私钥/下单。
原则 P3.4：带 User-Agent、超时、退避重试。
原则 P0.4：失败显性 —— 重试耗尽抛异常，由上层如实标记"数据不可用"，不静默吞错。
"""
import time
import requests

from . import config


class PolymarketClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": config.USER_AGENT})

    def _get(self, url: str, params: dict | None = None):
        last_err = None
        for attempt in range(config.HTTP_RETRIES):
            try:
                r = self.s.get(url, params=params, timeout=config.HTTP_TIMEOUT)
                if r.status_code == 200:
                    return r.json()
                # 429/5xx 退避重试；其他状态码直接抛
                if r.status_code in (429, 500, 502, 503, 504):
                    last_err = f"HTTP {r.status_code}"
                else:
                    r.raise_for_status()
            except requests.RequestException as e:
                last_err = str(e)
            sleep = config.HTTP_BACKOFF * (2 ** attempt)
            time.sleep(sleep)
        raise RuntimeError(f"抓取失败 {url} params={params}: {last_err}")

    def get_events_page(self, *, tag_id=None, series_id=None, active=True,
                        closed=False, order="volume", ascending=False,
                        limit=config.PAGE_LIMIT, offset=0):
        params = {"limit": limit, "offset": offset,
                  "active": str(active).lower(), "closed": str(closed).lower()}
        if order:
            params["order"] = order
            params["ascending"] = str(ascending).lower()
        if tag_id:
            params["tag_id"] = tag_id
        if series_id:
            params["series_id"] = series_id
        data = self._get(f"{config.GAMMA_BASE}/events", params)
        return data if isinstance(data, list) else data.get("data", [])

    def get_all_events(self, *, tag_id=None, series_id=None, active=True,
                       closed=False, order="volume", ascending=False, max_pages=12):
        """翻页拉全（单页硬上限100）。"""
        out, offset = [], 0
        for _ in range(max_pages):
            page = self.get_events_page(tag_id=tag_id, series_id=series_id,
                                        active=active, closed=closed, order=order,
                                        ascending=ascending, offset=offset)
            out.extend(page)
            if len(page) < config.PAGE_LIMIT:
                break
            offset += config.PAGE_LIMIT
        return out
