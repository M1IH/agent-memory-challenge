#!/usr/bin/env python3
"""Full 评测期间保活：让 Railway Free 容器不进入休眠。

背景（实测，2026-11-04）：
  - Railway Free 强制 sleepApplication=true，空闲约 5-11 分钟即 Stopping。
  - 冷启动实测 19 分钟（容器启动->uvicorn 4 min + 恢复->status=ok 15 min）。
  - 官方 Add 重试预算约 10 分钟（32 次 @ ~20s 退避）。
  - 所以一旦休眠，评测的 Add/Search 必然 503 失败。

策略：每 45 秒 GET /health，并校验响应体 status == "ok"。
  不能用 HTTP 200 判断：恢复期间 /health 返回 200 + {"status":"recovering"}。
  容器启动需要 3-5 分钟，所以 timeout 必须大于冷启动，否则会把唤醒中的请求误判为失败。

用法：
  python scripts/keepalive.py --hours 96 --log <path> --stop-file <path>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import httpx

URL = "https://api-production-40d75.up.railway.app/health"
INTERVAL_SECONDS = 45
TIMEOUT_SECONDS = 120  # 必须 > 冷启动的 uvicorn 就绪时间(约 4 min)? 否：单请求超时 120s 足够，
                       # 唤醒由连续请求驱动，不靠单次请求等待。


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def probe(client: httpx.Client) -> str:
    """返回 '200 ok' / '200 recovering' / 错误摘要。"""
    try:
        response = client.get(URL)
    except Exception as exc:  # noqa: BLE001 - 记录任意网络异常摘要
        return f"ERR {type(exc).__name__}: {str(exc)[:80]}"
    body = (response.text or "").strip()
    try:
        status = json.loads(body).get("status", "?")
    except Exception:  # noqa: BLE001
        status = "invalid-body"
    return f"{response.status_code} {status}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=96.0)
    parser.add_argument("--log", default=os.path.join(os.environ.get("TEMP", "."), "aml-keepalive.log"))
    parser.add_argument("--stop-file", default=os.path.join(os.environ.get("TEMP", "."), "aml-keepalive.stop"))
    args = parser.parse_args()

    deadline = dt.datetime.now() + dt.timedelta(hours=args.hours)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

    with httpx.Client(timeout=TIMEOUT_SECONDS, trust_env=False) as client, \
            open(args.log, "a", encoding="utf-8", buffering=1) as log:
        while dt.datetime.now() < deadline:
            if os.path.exists(args.stop_file):
                log.write(f"{now_iso()} STOPPED by stop-file\n")
                return 0
            result = probe(client)
            log.write(f"{now_iso()} {result}\n")
            time.sleep(INTERVAL_SECONDS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
