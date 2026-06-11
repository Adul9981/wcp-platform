"""数据自动刷新调度器。

后台定时跑 pipeline，保持行情新鲜、及时捕捉先发机会。
原则 P3.5 尊重数据源：默认间隔较宽(30min)，可配；阻塞型网络调用放线程池。
原则 P0.4 失败显性：刷新失败记录到 status，不静默。
"""
import asyncio
import time
import traceback
from datetime import datetime, timezone

from . import config, pipeline

# 刷新状态（供 /refresh-status 暴露，P0.4 失败可见）
status = {
    "enabled": True,
    "interval_min": config.REFRESH_INTERVAL_MIN,
    "runs": 0,
    "last_run": None,        # ISO
    "last_ok": None,         # bool
    "last_error": None,      # str
    "last_result": None,     # dict
    "running": False,
}

_task = None


def run_once() -> dict:
    """同步跑一次 pipeline，更新 status。供后台循环与手动触发共用。"""
    status["running"] = True
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = pipeline.run(verbose=False)
        status.update(last_run=started, last_ok=True, last_error=None,
                      last_result=result, runs=status["runs"] + 1)
        return result
    except Exception as e:
        status.update(last_run=started, last_ok=False,
                      last_error=f"{type(e).__name__}: {e}",
                      runs=status["runs"] + 1)
        traceback.print_exc()
        raise
    finally:
        status["running"] = False


async def _loop():
    interval = config.REFRESH_INTERVAL_MIN * 60
    while status["enabled"]:
        try:
            # 阻塞型(网络+DB)放线程池，不卡事件循环
            await asyncio.to_thread(run_once)
        except Exception:
            pass  # 已记进 status，继续下一轮
        await asyncio.sleep(interval)


def start():
    """启动后台刷新循环（FastAPI 启动时调用）。"""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
    return _task


def stop():
    status["enabled"] = False
    if _task:
        _task.cancel()
