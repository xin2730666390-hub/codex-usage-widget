# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as dt
import json
import locale
import math
import os
import pathlib
import queue
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import unittest
from typing import Any, Callable

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # pragma: no cover - reported by run_app()
    tk = None
    messagebox = None

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
except Exception:  # pragma: no cover - tests cover non-UI logic without PIL
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None
    ImageTk = None


APP_NAME = "Codex Usage Widget"
APP_VERSION = 2
APP_DIR = pathlib.Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets"
ICON_PATH = ASSET_DIR / "codex-usage.ico"
CODEX_MARK_PATH = ASSET_DIR / "codex-color.png"


def default_data_dir() -> pathlib.Path:
    if sys.platform == "darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / "CodexUsageWidget"
    if os.environ.get("APPDATA"):
        return pathlib.Path(os.environ["APPDATA"]) / "CodexUsageWidget"
    return APP_DIR / "CodexUsageWidget"


DATA_DIR = default_data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
CACHE_PATH = DATA_DIR / "limit_sample.json"
LOG_PATH = DATA_DIR / "widget.log"

FIVE_HOUR_MINUTES = 5 * 60
WEEKLY_MINUTES = 7 * 24 * 60

DEFAULT_CONFIG: dict[str, Any] = {
    "refresh_seconds": 25,
    "always_on_top": True,
    "window_x": None,
    "window_y": None,
    "codex_home": None,
    "language": "system",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_name": "Codex Usage Widget",
        "subtitle": "quota at a glance",
        "status_refreshing": "Refreshing",
        "status_unchanged": "No update",
        "status_cache": "Cached",
        "status_waiting": "Waiting",
        "status_stale": "Needs refresh",
        "status_live": "Live",
        "window_5h": "5H window",
        "window_7d": "7D window",
        "used": "Used",
        "used_short": "Used",
        "waiting": "Waiting",
        "waiting_snapshot": "Waiting snapshot",
        "stale_snapshot": "Waiting snapshot",
        "reset": " reset",
        "unknown": "Unknown",
        "unknown_time": "Unknown time",
        "reset_reached": "Reset reached",
        "minute_after": " min left",
        "hour_after": " h left",
        "hour_min_after": "{hours} h {mins} m left",
        "day_after": "{days} d left",
        "day_hour_after": "{days} d {hours} h left",
        "just_now": "Just now",
        "minute_ago": "{value} min ago",
        "hour_ago": "{value} h ago",
        "day_ago": "{value} d ago",
        "footer_refreshing": "Refreshing",
        "footer_unchanged": "No update · {age}",
        "footer_updated": "Updated {age}",
        "footer_cache": "Cached · {age}",
        "footer_waiting": "Waiting for Codex limit data",
        "menu_refresh": "Refresh now",
        "menu_topmost": "Always on top / off",
        "menu_reset": "Reset to top right",
        "menu_quit": "Quit",
        "pending_read": "Reading Codex limits",
        "pending_refresh": "Finding latest limit snapshot",
        "manual_unchanged": "Refresh finished, but no new limit snapshot was found",
        "tk_missing": "Cannot start window UI: tkinter is unavailable.",
        "pillow_missing": "Cannot start window UI: Pillow is unavailable.",
        "ui_crashed": "Widget failed to start. Log file:\n{path}",
        "arg_test": "Run self tests",
        "arg_include_ui": "Include UI smoke test",
        "arg_snapshot": "Print current limit snapshot",
        "arg_make_icon": "Regenerate high-resolution icon",
        "note_no_snapshot": "No new limit snapshot was found",
        "note_new_record": "It will refresh after Codex writes a new record",
        "note_unrecognized": "Limit records were found, but 5-hour or 7-day windows were not recognized",
        "note_format_changed": "Codex local record format may have changed",
        "note_stale": "A limit window has reached its reset point. It will update after your next Codex activity",
        "note_local": "From local Codex limit records",
        "note_cache": "Showing cached data",
        "note_cache_fallback": "Live read failed, showing last successful data: {error}",
        "note_cache_no_new": "No fresh snapshot yet, showing last successful data",
        "note_failed": "Read failed temporarily",
    },
    "zh": {
        "app_name": "Codex 用量小组件",
        "subtitle": "额度一眼看清",
        "status_refreshing": "刷新中",
        "status_unchanged": "无新快照",
        "status_cache": "缓存",
        "status_waiting": "等待数据",
        "status_stale": "待刷新",
        "status_live": "实时",
        "window_5h": "5 小时窗口",
        "window_7d": "1 周窗口",
        "used": "已用",
        "used_short": "用",
        "waiting": "等待",
        "waiting_snapshot": "等待快照",
        "stale_snapshot": "等待新快照",
        "reset": "重置",
        "unknown": "未知",
        "unknown_time": "未知时间",
        "reset_reached": "已到重置时间",
        "minute_after": " 分钟后",
        "hour_after": " 小时后",
        "hour_min_after": "{hours} 小时 {mins} 分后",
        "day_after": "{days} 天后",
        "day_hour_after": "{days} 天 {hours} 小时后",
        "just_now": "刚刚",
        "minute_ago": "{value} 分钟前",
        "hour_ago": "{value} 小时前",
        "day_ago": "{value} 天前",
        "footer_refreshing": "正在刷新",
        "footer_unchanged": "无新快照 · {age}",
        "footer_updated": "更新 {age}",
        "footer_cache": "缓存 · {age}",
        "footer_waiting": "等待 Codex 额度数据",
        "menu_refresh": "立即刷新",
        "menu_topmost": "置顶 / 取消置顶",
        "menu_reset": "回到右上角",
        "menu_quit": "退出",
        "pending_read": "正在读取 Codex 额度",
        "pending_refresh": "正在查找最新额度快照",
        "manual_unchanged": "刷新完成，但没有新的额度快照",
        "tk_missing": "无法启动窗口组件：tkinter 不可用。",
        "pillow_missing": "无法启动窗口组件：Pillow 不可用。",
        "ui_crashed": "小组件启动失败，日志在：\n{path}",
        "arg_test": "运行自测",
        "arg_include_ui": "自测时包含窗口烟雾测试",
        "arg_snapshot": "打印当前读取到的额度快照",
        "arg_make_icon": "重新生成高分辨率图标",
        "note_no_snapshot": "没有找到新的额度快照",
        "note_new_record": "Codex 写入新记录后会自动刷新",
        "note_unrecognized": "读到了额度记录，但没有识别出 5 小时或 1 周窗口",
        "note_format_changed": "Codex 记录格式可能更新了",
        "note_stale": "额度窗口已经到过重置点，继续一次 Codex 后会更新",
        "note_local": "来自 Codex 本地额度记录",
        "note_cache": "显示缓存数据",
        "note_cache_fallback": "当前读取失败，显示上次成功数据：{error}",
        "note_cache_no_new": "暂时没读到新快照，显示上次成功数据",
        "note_failed": "暂时读取失败",
    },
}


def system_language() -> str:
    configured = os.environ.get("CODEX_USAGE_WIDGET_LANG", "").strip().lower()
    if configured:
        return "zh" if configured.startswith("zh") else "en"
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            buffer = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                return "zh" if buffer.value.lower().startswith("zh") else "en"
    candidates = [
        locale.getlocale()[0],
        os.environ.get("LANG"),
        os.environ.get("LANGUAGE"),
    ]
    for value in candidates:
        if value and str(value).lower().startswith("zh"):
            return "zh"
    return "en"


CURRENT_LANGUAGE = system_language()


def tr(key: str, **kwargs: Any) -> str:
    text = TRANSLATIONS.get(CURRENT_LANGUAGE, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def log_line(message: str) -> None:
    try:
        ensure_data_dir()
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def load_json(path: pathlib.Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_line(f"Failed to load {path}: {exc}")
    return default


def atomic_write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def clean_int(value: Any, minimum: int | None = None, maximum: int | None = None) -> int | None:
    if value in ("", None):
        return None
    try:
        parsed = int(float(str(value).replace(",", "").strip()))
    except Exception:
        return None
    if minimum is not None and parsed < minimum:
        return None
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def clean_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        parsed = float(str(value).strip())
    except Exception:
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    user_config = load_json(CONFIG_PATH, {})
    if isinstance(user_config, dict):
        config.update(user_config)
    config["refresh_seconds"] = clean_int(config.get("refresh_seconds"), 10, 3600) or 25
    config["window_x"] = clean_int(config.get("window_x"))
    config["window_y"] = clean_int(config.get("window_y"))
    config["always_on_top"] = bool(config.get("always_on_top", True))
    if config.get("codex_home"):
        config["codex_home"] = str(config["codex_home"])
    return config


def save_config(config: dict[str, Any]) -> None:
    to_write = dict(DEFAULT_CONFIG)
    to_write.update(config)
    atomic_write_json(CONFIG_PATH, to_write)


def codex_home_from_config(config: dict[str, Any]) -> pathlib.Path:
    configured = config.get("codex_home") or os.environ.get("CODEX_HOME")
    if configured:
        return pathlib.Path(str(configured)).expanduser()
    return pathlib.Path(os.environ.get("USERPROFILE") or str(pathlib.Path.home())) / ".codex"


def now_ts() -> float:
    return time.time()


def parse_event_timestamp(value: Any) -> float | None:
    if value in ("", None):
        return None
    numeric = clean_float(value)
    if numeric is not None and numeric > 0:
        return numeric / 1000 if numeric > 10_000_000_000 else numeric
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except Exception:
        return None


def format_local_time(timestamp: Any, include_date: bool = False) -> str:
    ts = clean_float(timestamp)
    if ts is None or ts <= 0:
        return tr("unknown")
    if ts > 10_000_000_000:
        ts /= 1000
    try:
        value = dt.datetime.fromtimestamp(ts).astimezone()
    except Exception:
        return tr("unknown")
    if include_date:
        return value.strftime("%m月%d日 %H:%M") if CURRENT_LANGUAGE == "zh" else value.strftime("%b %d %H:%M")
    return value.strftime("%H:%M")


def format_relative(timestamp: Any, now: float | None = None) -> str:
    ts = clean_float(timestamp)
    if ts is None or ts <= 0:
        return tr("unknown")
    if ts > 10_000_000_000:
        ts /= 1000
    now = now_ts() if now is None else now
    delta = ts - now
    if delta <= 0:
        return tr("reset_reached")
    minutes = int(round(delta / 60))
    if minutes < 60:
        return f"{max(1, minutes)}{tr('minute_after')}"
    hours, mins = divmod(minutes, 60)
    if hours < 36:
        return tr("hour_min_after", hours=hours, mins=mins) if mins else f"{hours}{tr('hour_after')}"
    days, hours = divmod(hours, 24)
    return tr("day_hour_after", days=days, hours=hours) if hours else tr("day_after", days=days)


def format_age(timestamp: Any, now: float | None = None) -> str:
    ts = clean_float(timestamp)
    if ts is None or ts <= 0:
        return tr("unknown_time")
    if ts > 10_000_000_000:
        ts /= 1000
    now = now_ts() if now is None else now
    age = max(0, int(now - ts))
    if age < 75:
        return tr("just_now")
    if age < 3600:
        return tr("minute_ago", value=age // 60)
    if age < 36 * 3600:
        return tr("hour_ago", value=age // 3600)
    return tr("day_ago", value=age // 86400)


def empty_window() -> dict[str, Any]:
    return {
        "available": False,
        "label": "",
        "used_percent": None,
        "remaining_percent": None,
        "reset_at": None,
        "window_minutes": None,
        "stale": False,
    }


def empty_sample(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = {} if config is None else config
    return {
        "app": tr("app_name"),
        "version": APP_VERSION,
        "ok": False,
        "source_state": "unavailable",
        "snapshot_at": now_ts(),
        "source_event_at": None,
        "source_path": None,
        "codex_home": str(codex_home_from_config(config)),
        "plan_type": None,
        "limit_id": None,
        "rate_limit_reached_type": None,
        "windows": {
            "five_hour": empty_window() | {"label": tr("window_5h")},
            "weekly": empty_window() | {"label": tr("window_7d")},
        },
        "errors": [],
        "note": "",
    }


def iter_rate_limit_payloads(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(node, dict):
            direct = node.get("rate_limits")
            if isinstance(direct, dict):
                found.append(direct)
            singular = node.get("rate_limit")
            if isinstance(singular, dict):
                found.append(singular)
            if any(key in node for key in ("primary", "secondary", "primary_window", "secondary_window")):
                found.append(node)
            for child in node.values():
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node:
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)

    walk(value)
    unique: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in found:
        ident = id(item)
        if ident not in seen:
            seen.add(ident)
            unique.append(item)
    return unique


def window_minutes_from(data: dict[str, Any]) -> int | None:
    minutes = clean_float(
        data.get("window_minutes")
        or data.get("limit_window_minutes")
        or data.get("rolling_window_minutes")
    )
    if minutes is not None and minutes > 0:
        return int(round(minutes))
    seconds = clean_float(
        data.get("limit_window_seconds")
        or data.get("window_seconds")
        or data.get("rolling_window_seconds")
    )
    if seconds is not None and seconds > 0:
        return int(round(seconds / 60))
    return None


def reset_timestamp_from(data: dict[str, Any]) -> float | None:
    return parse_event_timestamp(data.get("resets_at") or data.get("reset_at") or data.get("resetAt"))


def normalize_window(data: dict[str, Any], label: str, now: float | None = None) -> dict[str, Any] | None:
    minutes = window_minutes_from(data)
    used = clean_float(data.get("used_percent") or data.get("usage_percent") or data.get("usedPercentage"))
    reset_at = reset_timestamp_from(data)
    if minutes is None and used is None and reset_at is None:
        return None
    used = clamp(used if used is not None else 0.0, 0.0, 100.0)
    remaining = clamp(100.0 - used, 0.0, 100.0)
    current = now_ts() if now is None else now
    return {
        "available": True,
        "label": label,
        "used_percent": round(used, 1),
        "remaining_percent": round(remaining, 1),
        "reset_at": reset_at,
        "window_minutes": minutes,
        "stale": bool(reset_at is not None and reset_at <= current),
    }


def candidate_windows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("primary", "secondary", "primary_window", "secondary_window"):
        value = raw.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    additional = raw.get("additional_rate_limits")
    if isinstance(additional, list):
        for item in additional:
            if isinstance(item, dict):
                rate_limit = item.get("rate_limit")
                candidates.append(rate_limit if isinstance(rate_limit, dict) else item)
    if window_minutes_from(raw) is not None or raw.get("used_percent") is not None:
        candidates.append(raw)
    return candidates


def normalize_rate_limits(raw: dict[str, Any], now: float | None = None) -> dict[str, dict[str, Any]]:
    windows = {
        "five_hour": empty_window() | {"label": tr("window_5h")},
        "weekly": empty_window() | {"label": tr("window_7d")},
    }
    for item in candidate_windows(raw):
        minutes = window_minutes_from(item)
        if minutes == FIVE_HOUR_MINUTES:
            normalized = normalize_window(item, tr("window_5h"), now=now)
            if normalized:
                windows["five_hour"] = normalized
        elif minutes == WEEKLY_MINUTES:
            normalized = normalize_window(item, tr("window_7d"), now=now)
            if normalized:
                windows["weekly"] = normalized

    if not windows["five_hour"]["available"]:
        primary = raw.get("primary") or raw.get("primary_window")
        if isinstance(primary, dict):
            normalized = normalize_window(primary, tr("window_5h"), now=now)
            if normalized:
                normalized["window_minutes"] = normalized["window_minutes"] or FIVE_HOUR_MINUTES
                windows["five_hour"] = normalized
    if not windows["weekly"]["available"]:
        secondary = raw.get("secondary") or raw.get("secondary_window")
        if isinstance(secondary, dict):
            normalized = normalize_window(secondary, tr("window_7d"), now=now)
            if normalized:
                normalized["window_minutes"] = normalized["window_minutes"] or WEEKLY_MINUTES
                windows["weekly"] = normalized
    return windows


def sample_has_windows(sample: dict[str, Any]) -> bool:
    windows = sample.get("windows")
    if not isinstance(windows, dict):
        return False
    return any(isinstance(item, dict) and item.get("available") for item in windows.values())


class CodexRateLimitReader:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.codex_home = codex_home_from_config(config)

    def read(self) -> dict[str, Any]:
        sample = empty_sample(self.config)
        latest = self._find_latest_rate_limits()
        if latest is None:
            sample["errors"].append(tr("note_no_snapshot"))
            sample["note"] = tr("note_new_record")
            return sample

        raw = latest["rate_limits"]
        windows = normalize_rate_limits(raw)
        sample["windows"] = windows
        sample["ok"] = sample_has_windows(sample)
        sample["source_state"] = "live" if sample["ok"] else "unavailable"
        sample["source_event_at"] = latest.get("timestamp")
        sample["source_path"] = str(latest.get("path"))
        sample["plan_type"] = raw.get("plan_type")
        sample["limit_id"] = raw.get("limit_id")
        sample["rate_limit_reached_type"] = raw.get("rate_limit_reached_type")
        stale_count = sum(1 for item in windows.values() if item.get("available") and item.get("stale"))
        if not sample["ok"]:
            sample["errors"].append(tr("note_unrecognized"))
            sample["note"] = tr("note_format_changed")
        elif stale_count:
            sample["note"] = tr("note_stale")
        else:
            sample["note"] = tr("note_local")
        return sample

    def _find_latest_rate_limits(self) -> dict[str, Any] | None:
        candidates = [
            item
            for item in (
                self._find_latest_rate_limits_in_logs(),
                self._find_latest_rate_limits_in_sessions(),
            )
            if item is not None
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: float(item.get("timestamp") or 0))

    def _find_latest_rate_limits_in_sessions(self) -> dict[str, Any] | None:
        sessions = self.codex_home / "sessions"
        if not sessions.exists():
            return None
        files = sorted(
            (path for path in sessions.rglob("*.jsonl") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        best: dict[str, Any] | None = None
        best_ts = -1.0
        for path in files[:500]:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        if '"rate_limit' not in line:
                            continue
                        try:
                            event = json.loads(line)
                        except Exception:
                            continue
                        event_ts = parse_event_timestamp(event.get("timestamp")) or path.stat().st_mtime
                        if event_ts < best_ts:
                            continue
                        for raw in iter_rate_limit_payloads(event):
                            windows = normalize_rate_limits(raw)
                            if not any(item.get("available") for item in windows.values()):
                                continue
                            best_ts = event_ts
                            best = {
                                "timestamp": event_ts,
                                "path": path,
                                "rate_limits": raw,
                            }
            except Exception as exc:
                log_line(f"Failed to inspect {path}: {exc}")
        return best

    def _connect_sqlite_ro(self, path: pathlib.Path) -> sqlite3.Connection:
        uri = path.resolve().as_uri() + "?mode=ro&cache=shared"
        con = sqlite3.connect(uri, uri=True, timeout=0.75)
        con.row_factory = sqlite3.Row
        with contextlib.suppress(Exception):
            con.execute("pragma query_only = true")
        return con

    def _find_latest_rate_limits_in_logs(self) -> dict[str, Any] | None:
        db = self.codex_home / "logs_2.sqlite"
        if not db.exists():
            return None
        try:
            con = self._connect_sqlite_ro(db)
            try:
                rows = con.execute(
                    """
                    select id, ts, ts_nanos, feedback_log_body
                    from logs
                    where target = 'codex_api::endpoint::responses_websocket'
                      and feedback_log_body like '%websocket event:%'
                      and feedback_log_body like '%codex.rate_limits%'
                    order by ts desc, ts_nanos desc
                    limit 1000
                    """
                ).fetchall()
            finally:
                con.close()
        except Exception as exc:
            log_line(f"Failed to inspect logs_2.sqlite: {exc}")
            return None

        decoder = json.JSONDecoder()
        marker = "websocket event: "
        for row in rows:
            body = str(row["feedback_log_body"] or "")
            idx = body.find(marker)
            if idx < 0:
                continue
            try:
                event, _end = decoder.raw_decode(body[idx + len(marker):].strip())
            except Exception:
                continue
            if not isinstance(event, dict) or event.get("type") != "codex.rate_limits":
                continue
            rate_limits = event.get("rate_limits")
            if not isinstance(rate_limits, dict):
                continue
            raw = dict(rate_limits)
            raw.setdefault("limit_id", "codex")
            raw.setdefault("plan_type", event.get("plan_type"))
            if "limit_reached" in rate_limits:
                raw.setdefault("rate_limit_reached_type", "primary" if rate_limits.get("limit_reached") else None)
            if not any(item.get("available") for item in normalize_rate_limits(raw).values()):
                continue
            return {
                "timestamp": float(row["ts"] or 0),
                "path": f"{db}#logs:{row['id']}",
                "rate_limits": raw,
            }
        return None


def read_snapshot(
    config: dict[str, Any] | None = None,
    cache: bool = True,
    cache_path: pathlib.Path = CACHE_PATH,
) -> dict[str, Any]:
    config = load_config() if config is None else config
    try:
        sample = CodexRateLimitReader(config).read()
        if sample.get("ok"):
            if cache:
                atomic_write_json(cache_path, sample)
            return sample

        cached = load_json(cache_path, None)
        if isinstance(cached, dict) and cached.get("version") == APP_VERSION and sample_has_windows(cached):
            cached = dict(cached)
            cached["source_state"] = "cache"
            cached["snapshot_at"] = now_ts()
            cached["errors"] = sample.get("errors", [])
            cached["note"] = tr("note_cache_no_new")
            return cached
        return sample
    except Exception as exc:
        log_line("Snapshot read crashed:\n" + traceback.format_exc())
        cached = load_json(cache_path, None)
        if isinstance(cached, dict) and cached.get("version") == APP_VERSION and sample_has_windows(cached):
            cached = dict(cached)
            cached["source_state"] = "cache"
            cached["snapshot_at"] = now_ts()
            cached["errors"] = [tr("note_cache_fallback", error=exc)]
            cached["note"] = tr("note_cache")
            return cached
        sample = empty_sample(config)
        sample["errors"].append(str(exc))
        sample["note"] = tr("note_failed")
        return sample


def set_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    with contextlib.suppress(Exception):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    with contextlib.suppress(Exception):
        ctypes.windll.user32.SetProcessDPIAware()


class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def rgba_to_abgr(red: int, green: int, blue: int, alpha: int) -> int:
    return ((alpha & 0xFF) << 24) | ((blue & 0xFF) << 16) | ((green & 0xFF) << 8) | (red & 0xFF)


def apply_windows_glass(root: tk.Tk) -> bool:
    if sys.platform != "win32":
        return False
    applied = False
    try:
        root.update_idletasks()
        hwnd = root.winfo_id()
    except Exception:
        return False

    with contextlib.suppress(Exception):
        value = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), ctypes.sizeof(value))

    with contextlib.suppress(Exception):
        value = ctypes.c_int(3)  # DWMSBT_TRANSIENTWINDOW, acrylic-like on Windows 11
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(value), ctypes.sizeof(value))
        applied = applied or result == 0

    with contextlib.suppress(Exception):
        accent = AccentPolicy()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = rgba_to_abgr(8, 13, 24, 210)
        data = WindowCompositionAttributeData()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)
        result = ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        applied = applied or bool(result)
    return applied


def apply_rounded_window_region(root: tk.Tk, width: int, height: int, radius: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        root.update_idletasks()
        hwnd = root.winfo_id()
        diameter = max(2, int(radius * 2))
        region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, int(width) + 1, int(height) + 1, diameter, diameter)
        if not region:
            return False
        result = ctypes.windll.user32.SetWindowRgn(hwnd, region, True)
        return bool(result)
    except Exception as exc:
        log_line(f"Failed to apply rounded window region: {exc}")
        return False


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if ImageFont is None:
        raise RuntimeError("Pillow is unavailable")
    windir = pathlib.Path(os.environ.get("WINDIR", r"C:\Windows"))
    mac_fonts = pathlib.Path("/System/Library/Fonts")
    mac_supplemental = pathlib.Path("/System/Library/Fonts/Supplemental")
    candidates = [
        mac_fonts / ("PingFang.ttc"),
        mac_supplemental / ("Arial Unicode.ttf"),
        mac_supplemental / ("Arial Bold.ttf" if bold else "Arial.ttf"),
        pathlib.Path("/Library/Fonts") / ("Arial Unicode.ttf"),
        windir / "Fonts" / ("msyhbd.ttc" if bold else "msyh.ttc"),
        windir / "Fonts" / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        windir / "Fonts" / ("arialbd.ttf" if bold else "arial.ttf"),
    ]
    for path in candidates:
        with contextlib.suppress(Exception):
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    suffix: str = "...",
) -> str:
    if text_width(draw, text, font) <= max_width:
        return text
    trimmed = text
    while trimmed and text_width(draw, trimmed + suffix, font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + suffix) if trimmed else suffix


def percent_text(value: Any) -> str:
    numeric = clean_float(value)
    if numeric is None:
        return "--%"
    if abs(numeric - round(numeric)) < 0.05:
        return f"{int(round(numeric))}%"
    return f"{numeric:.1f}%"


def health_color(remaining: Any) -> str:
    value = clean_float(remaining)
    if value is None:
        return "#8E8E93"
    if value >= 60:
        return "#34C759"
    if value >= 25:
        return "#007AFF"
    if value >= 12:
        return "#FF9500"
    return "#FF3B30"


class CardRenderer:
    WIDTH = 304
    HEIGHT = 536
    SCALE = 2
    KEY = "#010203"

    def __init__(self) -> None:
        if Image is None or ImageDraw is None or ImageFilter is None:
            raise RuntimeError("Pillow is unavailable")
        self.codex_mark = self._load_codex_mark()

    def _load_codex_mark(self) -> Image.Image | None:
        if Image is None or not CODEX_MARK_PATH.exists():
            return None
        try:
            icon = Image.open(CODEX_MARK_PATH).convert("RGBA")
            return icon.resize((self.sc(34), self.sc(34)), Image.Resampling.LANCZOS)
        except Exception as exc:
            log_line(f"Failed to load Codex mark: {exc}")
            return None

    def sc(self, value: float) -> int:
        return int(round(value * self.SCALE))

    def xy(self, *values: float) -> tuple[int, ...]:
        return tuple(self.sc(value) for value in values)

    def render(self, sample: dict[str, Any] | None, hover: bool = False) -> Image.Image:
        sample = empty_sample() if sample is None else sample
        scale = self.SCALE
        width, height = self.WIDTH * scale, self.HEIGHT * scale
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        image = self._paint_acrylic_panel(image, hover=hover)
        draw = ImageDraw.Draw(image)

        self._draw_header(image, draw, sample)
        self._draw_primary_limit(draw, sample)
        self._draw_week_limit(draw, sample)
        self._draw_footer(draw, sample)

        rendered = image.convert("RGB").resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
        return self._apply_window_corner_mask(rendered)

    def _apply_window_corner_mask(self, image: Image.Image) -> Image.Image:
        background = Image.new("RGB", image.size, self.KEY)
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, image.size[0] - 1, image.size[1] - 1), radius=22, fill=255)
        background.paste(image, (0, 0), mask)
        return background

    def _paint_acrylic_panel(self, image: Image.Image, hover: bool = False) -> Image.Image:
        width, height = image.size
        x1, y1, x2, y2 = 0, 0, width - 1, height - 1
        mask = Image.new("L", (width, height), 255)

        panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        for y in range(y1, y2 + 1):
            ratio = (y - y1) / max(1, y2 - y1)
            if hover:
                red = int(34 - 12 * ratio)
                green = int(44 - 14 * ratio)
                blue = int(62 - 18 * ratio)
            else:
                red = int(18 - 8 * ratio)
                green = int(26 - 10 * ratio)
                blue = int(42 - 14 * ratio)
            panel_draw.line((x1, y, x2, y), fill=(red, green, blue, 255))
        panel.putalpha(mask)
        image = Image.alpha_composite(image, panel)

        highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        hdraw = ImageDraw.Draw(highlight)
        for offset in range(0, 130, 2):
            alpha = max(0, (42 if hover else 30) - offset // 4)
            hdraw.line(self.xy(-30, 44 + offset, 336, -52 + offset), fill=(255, 255, 255, alpha), width=self.sc(1))
        hdraw.rectangle(self.xy(0, 0, 304, 96), fill=(255, 255, 255, 18 if hover else 11))
        hdraw.rectangle(self.xy(0, 410, 304, 536), fill=(22, 163, 74, 12 if hover else 8))
        highlight.putalpha(Image.composite(highlight.getchannel("A"), Image.new("L", (width, height), 0), mask))
        image = Image.alpha_composite(image, highlight)

        noise = Image.effect_noise((width, height), 9).convert("L")
        noise_alpha = noise.point(lambda value: (10 if hover else 7) if value > 134 else 0)
        noise_alpha = Image.composite(noise_alpha, Image.new("L", (width, height), 0), mask)
        noise_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        noise_layer.putalpha(noise_alpha)
        return Image.alpha_composite(image, noise_layer)

    def _font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        return load_font(self.sc(size), bold=bold)

    def _draw_header(self, image: Image.Image, draw: ImageDraw.ImageDraw, sample: dict[str, Any]) -> None:
        ink = "#F8FAFC"
        muted = "#94A3B8"
        self._draw_codex_mark(image, draw, 38, 38)

        draw.text(self.xy(68, 19), "Codex Limit", font=self._font(18, True), fill=ink)
        draw.text(self.xy(69, 45), tr("subtitle"), font=self._font(10, True), fill=muted)
        pill_text = self._status_text(sample)
        status_color = self._status_color(sample)
        pill_width = min(132, max(78, int(text_width(draw, pill_text, self._font(10, True)) / self.SCALE) + 42))
        pill_x2 = 286
        pill_x1 = pill_x2 - pill_width
        draw.rounded_rectangle(self.xy(pill_x1, 70, pill_x2, 98), radius=self.sc(12), fill="#18263A")
        draw.ellipse(self.xy(pill_x1 + 13, 80, pill_x1 + 22, 89), fill=status_color)
        draw.text(self.xy(pill_x1 + 32, 76), pill_text, font=self._font(10, True), fill="#E2E8F0")

        draw.rounded_rectangle(self.xy(205, 19, 245, 55), radius=self.sc(12), fill="#1B2A3E")
        self._draw_refresh_icon(draw, 225, 37, "#C7D2FE")
        draw.rounded_rectangle(self.xy(252, 19, 292, 55), radius=self.sc(12), fill="#142033")
        self._draw_close_icon(draw, 272, 37, "#CBD5E1")

    def _status_text(self, sample: dict[str, Any]) -> str:
        if sample.get("refreshing"):
            return tr("status_refreshing")
        if sample.get("refresh_result") == "unchanged":
            return tr("status_unchanged")
        if sample.get("source_state") == "cache":
            return tr("status_cache")
        if not sample.get("ok"):
            return tr("status_waiting")
        windows = sample.get("windows") or {}
        return tr("status_live")

    def _status_color(self, sample: dict[str, Any]) -> str:
        text = self._status_text(sample)
        if text == tr("status_refreshing"):
            return "#2563EB"
        if text == tr("status_live"):
            return "#34C759"
        if text in (tr("status_cache"), tr("status_stale"), tr("status_unchanged")):
            return "#FF9500"
        return "#FF3B30"

    def _draw_refresh_icon(self, draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
        box = self.xy(cx - 8, cy - 8, cx + 8, cy + 8)
        draw.arc(box, start=25, end=320, fill=color, width=self.sc(2))
        draw.polygon([self.xy(cx + 7, cy - 8), self.xy(cx + 14, cy - 8), self.xy(cx + 10, cy - 2)], fill=color)

    def _draw_close_icon(self, draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str) -> None:
        draw.line([self.xy(cx - 5, cy - 5), self.xy(cx + 5, cy + 5)], fill=color, width=self.sc(2))
        draw.line([self.xy(cx + 5, cy - 5), self.xy(cx - 5, cy + 5)], fill=color, width=self.sc(2))

    def _draw_codex_mark(self, image: Image.Image, draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
        if self.codex_mark is not None:
            image.alpha_composite(self.codex_mark, dest=self.xy(cx - 17, cy - 17))
            return
        draw.rounded_rectangle(self.xy(cx - 17, cy - 17, cx + 17, cy + 17), radius=self.sc(10), fill="#0B1220")
        draw.rounded_rectangle(self.xy(cx - 16, cy - 16, cx + 16, cy + 16), radius=self.sc(9), outline="#263B5A", width=self.sc(1))
        points = [
            ((cx - 3, cy - 12), (cx + 9, cy - 6)),
            ((cx + 9, cy - 6), (cx + 10, cy + 7)),
            ((cx + 10, cy + 7), (cx - 2, cy + 13)),
            ((cx - 2, cy + 13), (cx - 13, cy + 5)),
            ((cx - 13, cy + 5), (cx - 10, cy - 8)),
            ((cx - 10, cy - 8), (cx - 3, cy - 12)),
        ]
        colors = ["#E0F2FE", "#BFDBFE", "#DBEAFE", "#E0F2FE", "#BFDBFE", "#F8FAFC"]
        for (start, end), color in zip(points, colors):
            self._rounded_line(draw, start, end, color, 4)
        draw.ellipse(self.xy(cx - 4, cy - 4, cx + 4, cy + 4), fill="#0B1220", outline="#E0F2FE", width=self.sc(2))

    def _rounded_line(self, draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int) -> None:
        scaled_width = self.sc(width)
        draw.line([self.xy(*start), self.xy(*end)], fill=color, width=scaled_width)
        radius = width / 2
        for x, y in (start, end):
            draw.ellipse(self.xy(x - radius, y - radius, x + radius, y + radius), fill=color)

    def _window_style(self, window: dict[str, Any]) -> tuple[str, float, bool, bool]:
        remaining = window.get("remaining_percent")
        available = bool(window.get("available"))
        stale = bool(window.get("stale"))
        if stale:
            return "#94A3B8", 0.0, available, stale
        if not available:
            return "#94A3B8", 0.0, available, stale
        ratio = clamp((clean_float(remaining) or 0.0) / 100.0, 0.0, 1.0)
        value = clean_float(remaining) or 0.0
        if value >= 60:
            return "#4ADE80", ratio, available, stale
        if value >= 25:
            return "#60A5FA", ratio, available, stale
        if value >= 12:
            return "#FBBF24", ratio, available, stale
        return "#F87171", ratio, available, stale

    def _remaining_label(self, window: dict[str, Any], stale: bool) -> str:
        if stale:
            return "--%"
        if not window.get("available"):
            return "--%"
        return percent_text(window.get("remaining_percent"))

    def _draw_primary_limit(self, draw: ImageDraw.ImageDraw, sample: dict[str, Any]) -> None:
        window = (sample.get("windows") or {}).get("five_hour") or empty_window()
        color, ratio, available, stale = self._window_style(window)
        if available and not stale:
            color = "#4ADE80"
        x1, y1, x2, y2 = 18, 118, 286, 324
        self._draw_soft_shadow(draw, x1, y1, x2, y2, 24)
        draw.rounded_rectangle(self.xy(x1, y1, x2, y2), radius=self.sc(24), fill="#111C2B")

        draw.text(self.xy(x1 + 22, y1 + 22), "5H", font=self._font(20, True), fill="#F8FAFC")
        label_font = self._font(12, True)
        label = fit_text(draw, tr("window_5h"), label_font, self.sc(88))
        draw.text(self.xy(x1 + 71, y1 + 30), label, font=label_font, fill="#94A3B8")

        used_text = tr("waiting") if stale else (f"{tr('used')} {percent_text(window.get('used_percent'))}" if available else tr("waiting"))
        draw.rounded_rectangle(self.xy(x2 - 102, y1 + 21, x2 - 18, y1 + 49), radius=self.sc(11), fill="#2A1F19")
        draw.text(self.xy(x2 - 60, y1 + 35), used_text, font=self._font(10, True), fill="#FDBA74", anchor="mm")

        main = self._remaining_label(window, stale)
        main_font = self._font(72 if not stale else 40, True)
        draw.text(self.xy(x1 + 22, y1 + 70), main, font=main_font, fill=color)

        reset = self._compact_relative(window.get("reset_at")) if available else tr("waiting_snapshot")
        reset = tr("stale_snapshot") if stale else f"{reset}{tr('reset')}"
        draw.text(self.xy(x1 + 24, y1 + 58), reset, font=self._font(13, True), fill="#CBD5E1")

        self._draw_progress(draw, x1 + 22, y2 - 34, x2 - 22, y2 - 18, ratio, color, available and not stale)

    def _draw_week_limit(self, draw: ImageDraw.ImageDraw, sample: dict[str, Any]) -> None:
        window = (sample.get("windows") or {}).get("weekly") or empty_window()
        color, ratio, available, stale = self._window_style(window)
        x1, y1, x2, y2 = 18, 336, 286, 482
        self._draw_soft_shadow(draw, x1, y1, x2, y2, 22)
        draw.rounded_rectangle(self.xy(x1, y1, x2, y2), radius=self.sc(22), fill="#101A29")

        draw.text(self.xy(x1 + 22, y1 + 22), "7D", font=self._font(18, True), fill="#F8FAFC")
        week_label_font = self._font(12, True)
        week_label = fit_text(draw, tr("window_7d"), week_label_font, self.sc(104))
        draw.text(self.xy(x1 + 66, y1 + 27), week_label, font=week_label_font, fill="#94A3B8")
        used_text = tr("waiting") if stale else (f"{tr('used_short')} {percent_text(window.get('used_percent'))}" if available else "--")
        draw.rounded_rectangle(self.xy(x2 - 82, y1 + 19, x2 - 18, y1 + 47), radius=self.sc(11), fill="#2A1F19")
        draw.text(self.xy(x2 - 50, y1 + 33), used_text, font=self._font(10, True), fill="#FDBA74", anchor="mm")

        main = self._remaining_label(window, stale)
        main_font = self._font(40 if not stale else 26, True)
        draw.text(self.xy(x1 + 22, y1 + 62), main, font=main_font, fill=color)

        reset = self._compact_relative(window.get("reset_at")) if available else tr("waiting_snapshot")
        reset = tr("stale_snapshot") if stale else f"{reset}{tr('reset')}"
        reset = fit_text(draw, reset, self._font(12, True), self.sc(128))
        draw.text(self.xy(x1 + 136, y1 + 78), reset, font=self._font(12, True), fill="#94A3B8")

        self._draw_progress(draw, x1 + 22, y2 - 30, x2 - 22, y2 - 16, ratio, color, available and not stale)

    def _draw_progress(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, ratio: float, color: str, active: bool) -> None:
        radius = self.sc((y2 - y1) / 2)
        draw.rounded_rectangle(self.xy(x1, y1, x2, y2), radius=radius, fill="#22334A")
        if not active:
            fill_x2 = x1 + max(10, int((x2 - x1) * clamp(ratio, 0.0, 1.0)))
            draw.rounded_rectangle(self.xy(x1, y1, fill_x2, y2), radius=radius, fill=color)
            return
        remaining_ratio = clamp(ratio, 0.0, 1.0)
        split_x = x1 + int((x2 - x1) * remaining_ratio)
        if split_x > x1:
            draw.rounded_rectangle(self.xy(x1, y1, split_x, y2), radius=radius, fill=color)
        if split_x < x2:
            draw.rounded_rectangle(self.xy(split_x, y1, x2, y2), radius=radius, fill="#F97316")
        if x1 < split_x < x2:
            draw.rectangle(self.xy(split_x - 1, y1, split_x + 1, y2), fill="#0B1220")

    def _draw_soft_shadow(self, draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int, radius: int) -> None:
        draw.rounded_rectangle(self.xy(x1 + 2, y1 + 4, x2 + 2, y2 + 5), radius=self.sc(radius), fill="#07101F")

    def _draw_metric_tile(
        self,
        draw: ImageDraw.ImageDraw,
        sample: dict[str, Any],
        key: str,
        box: tuple[int, int, int, int],
        accent: str,
        primary: bool,
    ) -> None:
        x1, y1, x2, y2 = box
        window = (sample.get("windows") or {}).get(key) or empty_window()
        remaining = window.get("remaining_percent")
        used = window.get("used_percent")
        available = bool(window.get("available"))
        stale = bool(window.get("stale"))
        color = "#94A3B8" if not available else health_color(remaining)
        if stale:
            color = "#FF9500"

        draw.rounded_rectangle(self.xy(x1, y1, x2, y2), radius=self.sc(24), fill="#F8FBFF")
        draw.rounded_rectangle(self.xy(x1 + 2, y1 + 2, x2 - 2, y2 - 2), radius=self.sc(22), outline="#FFFFFF", width=self.sc(1))

        label_font = self._font(17 if primary else 15, True)
        small_font = self._font(13 if primary else 12)
        draw.text(self.xy(x1 + 22, y1 + 20), tr("window_5h" if key == "five_hour" else "window_7d"), font=label_font, fill="#0F172A")

        used_text = f"{tr('used')} {percent_text(used)}" if available else tr("status_waiting")
        used_w = text_width(draw, used_text, self._font(11, True)) / self.SCALE + 24
        draw.rounded_rectangle(self.xy(x2 - used_w - 20, y1 + 18, x2 - 20, y1 + 43), radius=self.sc(12), fill=self._soft_color(accent))
        draw.text(self.xy(x2 - used_w - 8, y1 + 24), used_text, font=self._font(11, True), fill="#334155")

        if stale:
            main = tr("status_stale")
            main_font = self._font(30 if primary else 22, True)
            reset_line = f"{tr('stale_snapshot')} {percent_text(remaining)}"
            helper_line = tr("waiting_snapshot")
        else:
            main = percent_text(remaining) if available else "--%"
            main_font = self._font(58 if primary else 42, True)
            reset_line = f"{self._compact_relative(window.get('reset_at'))}{tr('reset')}" if available else tr("waiting_snapshot")
            helper_line = ""

        reset_line = fit_text(draw, reset_line, small_font, self.sc((x2 - x1) - 44))
        draw.text(self.xy(x1 + 24, y1 + 51), reset_line, font=small_font, fill="#64748B")

        value_y = y1 + (75 if primary else 75)
        draw.text(self.xy(x1 + 22, value_y), main, font=main_font, fill=color)
        helper_x = x1 + 22 + (text_width(draw, main, main_font) / self.SCALE) + 10
        if available and not stale and helper_x < x2 - 38:
            draw.text(self.xy(helper_x, value_y + (32 if primary else 22)), helper_line, font=self._font(14 if primary else 12, True), fill="#475569")

        bar_x1, bar_y1, bar_x2, bar_y2 = x1 + 24, y2 - 24, x2 - 24, y2 - 14
        draw.rounded_rectangle(self.xy(bar_x1, bar_y1, bar_x2, bar_y2), radius=self.sc(5), fill="#E3EBF5")
        if available and not stale:
            ratio = clamp((clean_float(remaining) or 0.0) / 100.0, 0.0, 1.0)
            fill_x2 = bar_x1 + max(8, int((bar_x2 - bar_x1) * ratio))
            draw.rounded_rectangle(self.xy(bar_x1, bar_y1, fill_x2, bar_y2), radius=self.sc(5), fill=color)
        elif stale:
            draw.rounded_rectangle(self.xy(bar_x1, bar_y1, bar_x1 + 34, bar_y2), radius=self.sc(5), fill=color)

    def _compact_relative(self, timestamp: Any) -> str:
        text = format_relative(timestamp)
        return text.replace(" ", "") if CURRENT_LANGUAGE == "zh" else text

    def _soft_color(self, color: str) -> str:
        if color == "#34C759":
            return "#E8F8ED"
        if color == "#007AFF":
            return "#E8F2FF"
        return "#EEF2F7"

    def _draw_footer(self, draw: ImageDraw.ImageDraw, sample: dict[str, Any]) -> None:
        source_event = sample.get("source_event_at")
        if sample.get("refreshing"):
            footer = tr("footer_refreshing")
        elif sample.get("refresh_result") == "unchanged":
            footer = tr("footer_unchanged", age=format_age(source_event))
        elif sample.get("ok"):
            footer = tr("footer_updated", age=format_age(source_event))
        else:
            errors = sample.get("errors") or []
            footer = errors[0] if errors else (sample.get("note") or tr("footer_waiting"))
        if sample.get("source_state") == "cache":
            footer = tr("footer_cache", age=format_age(source_event))
        footer = fit_text(draw, footer, self._font(12), self.sc(178))
        draw.text(self.xy(22, 496), footer, font=self._font(12, True), fill="#94A3B8")

        plan = str(sample.get("plan_type") or "Codex").upper()
        plan = fit_text(draw, plan, self._font(12, True), self.sc(62), suffix="")
        draw.rounded_rectangle(self.xy(212, 488, 282, 512), radius=self.sc(10), fill="#172437")
        draw.text(self.xy(247, 500), plan, font=self._font(11, True), fill="#CBD5E1", anchor="mm")


class UsageWidget:
    WIDTH = CardRenderer.WIDTH
    HEIGHT = CardRenderer.HEIGHT
    KEY = CardRenderer.KEY

    def __init__(
        self,
        root: tk.Tk,
        config: dict[str, Any],
        snapshot_func: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ):
        self.root = root
        self.config = config
        self.snapshot_func = snapshot_func or (lambda cfg: read_snapshot(cfg, cache=True))
        self.renderer = CardRenderer()
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.refreshing = False
        self.closed = False
        self.drag_origin: tuple[int, int, int, int] | None = None
        self.drag_moved = False
        self.hovered = False
        self.current_sample: dict[str, Any] | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self._build_window()
        self._make_menu()
        self._place_initial()
        self._apply_window_shape()
        self._set_image(empty_sample(self.config) | {"note": tr("pending_read")})
        self.refresh()
        self._poll_queue()
        self._schedule_refresh()
        self._ensure_visible_loop()

    def _build_window(self) -> None:
        self.root.title(tr("app_name"))
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.root.configure(bg=self.KEY)
        self.root.attributes("-topmost", bool(self.config.get("always_on_top", True)))
        with contextlib.suppress(Exception):
            self.root.attributes("-alpha", 1.0)
        with contextlib.suppress(Exception):
            self.root.wm_attributes("-transparentcolor", self.KEY)
        apply_windows_glass(self.root)
        self.label = tk.Label(self.root, bg=self.KEY, bd=0, highlightthickness=0)
        self.label.pack(fill="both", expand=True)
        self.label.bind("<ButtonPress-1>", self._begin_drag)
        self.label.bind("<B1-Motion>", self._drag)
        self.label.bind("<ButtonRelease-1>", self._end_drag)
        self.label.bind("<Button-3>", self._show_menu)
        self.label.bind("<Enter>", lambda _event: self._set_hovered(True))
        self.label.bind("<Leave>", lambda _event: self._set_hovered(False))
        self.root.bind("<Escape>", lambda _event: self.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _make_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label=tr("menu_refresh"), command=lambda: self.refresh(force=True))
        self.menu.add_command(label=tr("menu_topmost"), command=self.toggle_topmost)
        self.menu.add_command(label=tr("menu_reset"), command=self.reset_position)
        self.menu.add_separator()
        self.menu.add_command(label=tr("menu_quit"), command=self.quit)

    def _place_initial(self) -> None:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = self.config.get("window_x")
        y = self.config.get("window_y")
        if x is None or y is None:
            x = sw - self.WIDTH - 34
            y = 58
        x = min(max(8, int(x)), max(8, sw - self.WIDTH - 8))
        y = min(max(8, int(y)), max(8, sh - self.HEIGHT - 48))
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _apply_window_shape(self) -> None:
        apply_rounded_window_region(self.root, self.WIDTH, self.HEIGHT, 22)

    def _set_image(self, sample: dict[str, Any]) -> None:
        self.current_sample = sample
        image = self.renderer.render(sample, hover=self.hovered)
        self.photo = ImageTk.PhotoImage(image)
        self.label.configure(image=self.photo)

    def _set_hovered(self, hovered: bool) -> None:
        if self.hovered == hovered or self.closed:
            return
        self.hovered = hovered
        with contextlib.suppress(Exception):
            self.root.attributes("-alpha", 0.78 if hovered else 1.0)
        if self.current_sample:
            self._set_image(self.current_sample)

    def _begin_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.drag_moved = False

    def _drag(self, event: tk.Event) -> None:
        if not self.drag_origin:
            return
        sx, sy, wx, wy = self.drag_origin
        dx, dy = event.x_root - sx, event.y_root - sy
        if abs(dx) > 3 or abs(dy) > 3:
            self.drag_moved = True
        self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def _end_drag(self, event: tk.Event) -> None:
        if not self.drag_moved:
            if self._inside(event.x, event.y, 200, 14, 250, 62):
                self.refresh(force=True)
                return
            if self._inside(event.x, event.y, 247, 14, 297, 62):
                self.quit()
                return
        self.config["window_x"] = self.root.winfo_x()
        self.config["window_y"] = self.root.winfo_y()
        save_config(self.config)

    def _inside(self, x: int, y: int, left: int, top: int, right: int, bottom: int) -> bool:
        return left <= x <= right and top <= y <= bottom

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def reset_position(self) -> None:
        sw = self.root.winfo_screenwidth()
        self.config["window_x"] = sw - self.WIDTH - 34
        self.config["window_y"] = 58
        save_config(self.config)
        self._place_initial()
        self._apply_window_shape()

    def toggle_topmost(self) -> None:
        self.config["always_on_top"] = not bool(self.config.get("always_on_top", True))
        self.root.attributes("-topmost", bool(self.config["always_on_top"]))
        save_config(self.config)

    def refresh(self, force: bool = False) -> None:
        if self.refreshing and not force:
            return
        self.refreshing = True
        previous_marker = self._source_marker(self.current_sample)
        if force and self.current_sample:
            pending = dict(self.current_sample)
            pending["refreshing"] = True
            pending["refresh_result"] = None
            pending["note"] = tr("pending_refresh")
            self._set_image(pending)

        def worker() -> None:
            try:
                sample = self.snapshot_func(dict(self.config))
            except Exception:
                log_line("Worker crashed:\n" + traceback.format_exc())
                sample = read_snapshot(dict(self.config), cache=True)
            if force:
                sample["manual_refresh"] = True
                sample["refresh_result"] = "updated" if self._source_marker(sample) != previous_marker else "unchanged"
                if sample["refresh_result"] == "unchanged":
                    sample["note"] = tr("manual_unchanged")
            self.queue.put(sample)

        threading.Thread(target=worker, daemon=True).start()

    def _source_marker(self, sample: dict[str, Any] | None) -> tuple[Any, Any] | None:
        if not sample:
            return None
        return sample.get("source_event_at"), sample.get("source_path")

    def _poll_queue(self) -> None:
        try:
            while True:
                sample = self.queue.get_nowait()
                self.refreshing = False
                self._set_image(sample)
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(250, self._poll_queue)

    def _schedule_refresh(self) -> None:
        if self.closed:
            return
        self.refresh()
        self.root.after(int(self.config.get("refresh_seconds", 25)) * 1000, self._schedule_refresh)

    def _ensure_visible_loop(self) -> None:
        if self.closed:
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if x < -self.WIDTH + 80 or y < -self.HEIGHT + 80 or x > sw - 50 or y > sh - 50:
            self.reset_position()
        self.root.after(7000, self._ensure_visible_loop)

    def quit(self) -> None:
        self.closed = True
        with contextlib.suppress(Exception):
            self.root.destroy()


def create_icon(path: pathlib.Path = ICON_PATH) -> pathlib.Path:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is unavailable")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((28, 30, 232, 232), radius=52, fill=(0, 0, 0, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((24, 18, 232, 226), radius=54, fill="#EAF4FF", outline="#FFFFFF", width=5)
    draw.ellipse((-34, -52, 190, 170), fill=(255, 255, 255, 65))
    draw.ellipse((108, 122, 302, 286), fill=(37, 99, 235, 42))
    draw.arc((62, 56, 194, 188), start=90, end=390, fill="#2563EB", width=22)
    draw.arc((83, 77, 173, 167), start=90, end=390, fill="#34C759", width=18)
    font = load_font(46, bold=True)
    draw.text((128, 126), "C", font=font, fill="#111827", anchor="mm")
    img.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def set_window_icon(root: tk.Tk) -> None:
    with contextlib.suppress(Exception):
        if ICON_PATH.exists():
            root.iconbitmap(str(ICON_PATH))


def run_app() -> int:
    if tk is None:
        print(tr("tk_missing"))
        return 2
    if Image is None or ImageTk is None:
        print(tr("pillow_missing"))
        return 2
    set_dpi_awareness()
    config = load_config()
    try:
        with contextlib.suppress(Exception):
            if not ICON_PATH.exists():
                create_icon(ICON_PATH)
        root = tk.Tk()
        set_window_icon(root)
        UsageWidget(root, config)
        root.mainloop()
        return 0
    except Exception:
        log_line("UI crashed:\n" + traceback.format_exc())
        if messagebox:
            with contextlib.suppress(Exception):
                messagebox.showerror(tr("app_name"), tr("ui_crashed", path=LOG_PATH))
        return 1


def write_session_event(codex_home: pathlib.Path, payload: dict[str, Any], timestamp: str = "2026-06-25T09:56:30.302Z") -> pathlib.Path:
    session_dir = codex_home / "sessions" / "2026" / "06" / "25"
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "rollout-test.jsonl"
    event = {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "rate_limits": payload,
        },
    }
    path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_logs_rate_limit_event(codex_home: pathlib.Path, payload: dict[str, Any], timestamp: int | None = None) -> pathlib.Path:
    codex_home.mkdir(parents=True, exist_ok=True)
    path = codex_home / "logs_2.sqlite"
    con = sqlite3.connect(path)
    try:
        con.execute(
            """
            create table logs (
                id integer primary key autoincrement,
                ts integer not null,
                ts_nanos integer not null,
                level text not null,
                target text not null,
                feedback_log_body text,
                module_path text,
                file text,
                line integer,
                thread_id text,
                process_uuid text,
                estimated_bytes integer not null default 0
            )
            """
        )
        event = {
            "type": "codex.rate_limits",
            "plan_type": payload.get("plan_type", "plus"),
            "rate_limits": {
                "allowed": True,
                "limit_reached": False,
                "primary": payload["primary"],
                "secondary": payload["secondary"],
            },
            "credits": None,
        }
        body = "stream_request: websocket event: " + json.dumps(event, ensure_ascii=False)
        con.execute(
            """
            insert into logs (ts, ts_nanos, level, target, feedback_log_body)
            values (?, ?, ?, ?, ?)
            """,
            (timestamp or int(now_ts()), 0, "TRACE", "codex_api::endpoint::responses_websocket", body),
        )
        con.commit()
    finally:
        con.close()
    return path


def example_rate_limits(reset_offset: int = 3600) -> dict[str, Any]:
    reset = int(now_ts()) + reset_offset
    return {
        "limit_id": "codex",
        "limit_name": None,
        "primary": {
            "used_percent": 46.0,
            "window_minutes": FIVE_HOUR_MINUTES,
            "resets_at": reset,
        },
        "secondary": {
            "used_percent": 16.0,
            "window_minutes": WEEKLY_MINUTES,
            "resets_at": reset + 6 * 24 * 3600,
        },
        "credits": None,
        "individual_limit": None,
        "plan_type": "plus",
        "rate_limit_reached_type": None,
    }


class ReaderTests(unittest.TestCase):
    def test_extracts_five_hour_and_weekly_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = pathlib.Path(td) / ".codex"
            write_session_event(home, example_rate_limits())
            sample = CodexRateLimitReader({"codex_home": str(home)}).read()
            self.assertTrue(sample["ok"])
            self.assertEqual(sample["plan_type"], "plus")
            self.assertEqual(sample["windows"]["five_hour"]["remaining_percent"], 54.0)
            self.assertEqual(sample["windows"]["weekly"]["remaining_percent"], 84.0)
            self.assertFalse(sample["windows"]["five_hour"]["stale"])

    def test_extracts_rate_limits_from_logs_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = pathlib.Path(td) / ".codex"
            write_logs_rate_limit_event(home, example_rate_limits())
            sample = CodexRateLimitReader({"codex_home": str(home)}).read()
            self.assertTrue(sample["ok"])
            self.assertIn("logs_2.sqlite#logs:", str(sample["source_path"]))
            self.assertEqual(sample["windows"]["five_hour"]["remaining_percent"], 54.0)
            self.assertEqual(sample["windows"]["weekly"]["remaining_percent"], 84.0)

    def test_handles_limit_window_seconds_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = pathlib.Path(td) / ".codex"
            reset = int(now_ts()) + 5000
            write_session_event(
                home,
                {
                    "rate_limit": {
                        "primary_window": {
                            "used_percent": 25,
                            "limit_window_seconds": FIVE_HOUR_MINUTES * 60,
                            "reset_at": reset,
                        },
                        "secondary_window": {
                            "used_percent": 5,
                            "limit_window_seconds": WEEKLY_MINUTES * 60,
                            "reset_at": reset + 10000,
                        },
                    },
                    "plan_type": "plus",
                },
            )
            sample = CodexRateLimitReader({"codex_home": str(home)}).read()
            self.assertEqual(sample["windows"]["five_hour"]["remaining_percent"], 75.0)
            self.assertEqual(sample["windows"]["weekly"]["remaining_percent"], 95.0)

    def test_marks_expired_window_stale_without_hiding_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = pathlib.Path(td) / ".codex"
            write_session_event(home, example_rate_limits(reset_offset=-30))
            sample = CodexRateLimitReader({"codex_home": str(home)}).read()
            self.assertTrue(sample["ok"])
            self.assertEqual(sample["windows"]["five_hour"]["remaining_percent"], 54.0)
            self.assertTrue(sample["windows"]["five_hour"]["stale"])

    def test_cache_fallback_when_live_read_has_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp = pathlib.Path(td)
            home = temp / ".codex"
            cached = empty_sample({"codex_home": str(home)})
            cached["ok"] = True
            cached["source_state"] = "live"
            cached["source_event_at"] = now_ts() - 60
            cached["windows"] = normalize_rate_limits(example_rate_limits())
            cache_path = temp / "cache.json"
            atomic_write_json(cache_path, cached)

            sample = read_snapshot({"codex_home": str(home)}, cache=True, cache_path=cache_path)
            self.assertTrue(sample["ok"])
            self.assertEqual(sample["source_state"], "cache")
            self.assertEqual(sample["windows"]["weekly"]["remaining_percent"], 84.0)

    def test_renderer_returns_nonblank_image(self) -> None:
        if Image is None:
            self.skipTest("Pillow unavailable")
        sample = empty_sample()
        sample["ok"] = True
        sample["source_state"] = "live"
        sample["source_event_at"] = now_ts()
        sample["plan_type"] = "plus"
        sample["windows"] = normalize_rate_limits(example_rate_limits())
        image = CardRenderer().render(sample)
        self.assertEqual(image.size, (CardRenderer.WIDTH, CardRenderer.HEIGHT))
        pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
        self.assertGreater(len(set(pixels)), 50)

    def test_renderer_supports_english_and_chinese(self) -> None:
        if Image is None:
            self.skipTest("Pillow unavailable")
        global CURRENT_LANGUAGE
        previous = CURRENT_LANGUAGE
        try:
            for language in ("en", "zh"):
                CURRENT_LANGUAGE = language
                sample = empty_sample()
                sample["ok"] = True
                sample["source_state"] = "live"
                sample["source_event_at"] = now_ts()
                sample["plan_type"] = "plus"
                sample["windows"] = normalize_rate_limits(example_rate_limits())
                image = CardRenderer().render(sample, hover=True)
                self.assertEqual(image.size, (CardRenderer.WIDTH, CardRenderer.HEIGHT))
                self.assertIn(tr("status_live"), TRANSLATIONS[language].values())
        finally:
            CURRENT_LANGUAGE = previous


def run_tests(include_ui: bool = False) -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReaderTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if include_ui:
        if tk is None or ImageTk is None:
            print("UI smoke skipped: tkinter or Pillow unavailable")
            return 1

        def fake_snapshot(_config: dict[str, Any]) -> dict[str, Any]:
            sample = empty_sample()
            sample["ok"] = True
            sample["source_state"] = "live"
            sample["source_event_at"] = now_ts()
            sample["plan_type"] = "plus"
            sample["windows"] = normalize_rate_limits(example_rate_limits())
            sample["note"] = "UI smoke"
            return sample

        set_dpi_awareness()
        root = tk.Tk()
        set_window_icon(root)
        widget = UsageWidget(root, dict(DEFAULT_CONFIG), snapshot_func=fake_snapshot)
        root.after(650, widget.quit)
        root.mainloop()
        print("UI smoke ok")
    return 0 if result.wasSuccessful() else 1


def print_snapshot() -> int:
    print(json.dumps(read_snapshot(load_config(), cache=False), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=tr("app_name"))
    parser.add_argument("--test", action="store_true", help=tr("arg_test"))
    parser.add_argument("--include-ui", action="store_true", help=tr("arg_include_ui"))
    parser.add_argument("--snapshot", action="store_true", help=tr("arg_snapshot"))
    parser.add_argument("--make-icon", action="store_true", help=tr("arg_make_icon"))
    args = parser.parse_args(argv)
    if args.test:
        return run_tests(include_ui=args.include_ui)
    if args.snapshot:
        return print_snapshot()
    if args.make_icon:
        print(create_icon())
        return 0
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
