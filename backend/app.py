#!/usr/bin/env python3
"""
Aiko Track 数据更新后端。

每天北京时间 00:00 拉取最新 SMM 数据，写入 index.html，再提交并推送到仓库。

启动:
    python3 -m backend

立即执行一次（不常驻）:
    python3 -m backend --once

环境变量:
    AUTO_PUSH=1          更新后自动 git commit / push（默认开启）
    UPDATE_TOKEN=...     手动触发接口的可选保护 token
    HOST=127.0.0.1
    PORT=8765
    GIT_REMOTE=origin
    GIT_BRANCH=main
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.git_ops import GitError, commit_and_push
from update_smm_data import run_update

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
JOB_ID = "daily_smm_update"
COMMIT_FILES = ["index.html"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("aiko-track")

_lock = threading.Lock()
_state = {
    "running": False,
    "last_run_at": None,
    "last_success_at": None,
    "last_error": None,
    "last_result": None,
}


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _now_beijing() -> datetime:
    return datetime.now(BEIJING_TZ)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def next_run_at() -> datetime | None:
    job = scheduler.get_job(JOB_ID)
    if not job or not job.next_run_time:
        return None
    return job.next_run_time.astimezone(BEIJING_TZ)


def run_daily_job(push: bool | None = None) -> dict:
    """Fetch data, update HTML, optionally commit and push."""
    if not _lock.acquire(blocking=False):
        raise RuntimeError("更新任务正在执行，请稍后重试")

    _state["running"] = True
    started = _now_beijing()
    _state["last_run_at"] = started
    _state["last_error"] = None

    should_push = _env_flag("AUTO_PUSH", True) if push is None else push
    try:
        result = run_update()
        git_result = {"committed": False, "pushed": False, "sha": None}
        if should_push and result.get("changed"):
            git_result = commit_and_push(
                ROOT,
                COMMIT_FILES,
                "update data",
                remote=os.getenv("GIT_REMOTE", "origin"),
                branch=os.getenv("GIT_BRANCH") or None,
            )
        elif should_push and not result.get("changed"):
            logger.info("页面数据无变化，跳过提交")

        payload = {
            **result,
            **git_result,
            "ran_at": started.isoformat(),
        }
        _state["last_success_at"] = _now_beijing()
        _state["last_result"] = payload
        logger.info(
            "数据更新完成 date=%s changed=%s pushed=%s",
            result.get("update_date"),
            result.get("changed"),
            git_result.get("pushed"),
        )
        return payload
    except Exception as exc:
        _state["last_error"] = str(exc)
        logger.exception("数据更新失败")
        raise
    finally:
        _state["running"] = False
        _lock.release()


scheduler = BackgroundScheduler(timezone=BEIJING_TZ)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler.add_job(
        run_daily_job,
        CronTrigger(hour=0, minute=0, timezone=BEIJING_TZ),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("定时任务已启动：每天 00:00 Asia/Shanghai")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Aiko Track Updater", lifespan=lifespan)


def _check_token(x_update_token: str | None, token: str | None) -> None:
    expected = os.getenv("UPDATE_TOKEN", "").strip()
    if not expected:
        return
    provided = x_update_token or token or ""
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid update token")


@app.get("/health")
def health():
    return {"ok": True, "service": "aiko-track-updater"}


@app.get("/api/status")
def status():
    return {
        "running": _state["running"],
        "last_run_at": _iso(_state["last_run_at"]),
        "last_success_at": _iso(_state["last_success_at"]),
        "last_error": _state["last_error"],
        "last_result": _state["last_result"],
        "next_run_at": _iso(next_run_at()),
        "auto_push": _env_flag("AUTO_PUSH", True),
        "timezone": "Asia/Shanghai",
    }


@app.post("/api/update")
def trigger_update(
    x_update_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
    push: bool | None = Query(default=None),
):
    _check_token(x_update_token, token)
    try:
        result = run_daily_job(push=push)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aiko Track 数据更新后端")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    parser.add_argument("--once", action="store_true", help="立即执行一次后退出")
    parser.add_argument("--no-push", action="store_true", help="只更新本地文件，不推送仓库")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.once:
        try:
            result = run_daily_job(push=not args.no_push)
        except Exception:
            sys.exit(1)
        print(result)
        return

    uvicorn.run(
        "backend.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
