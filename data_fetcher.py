from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

from config import CFG, ensure_dirs


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_or_fetch_av(
    cache_path: Path,
    fetch_fn,
    min_bytes: int = 200,
) -> dict:
    """
    Generic cache loader:
    - If cache exists and looks valid -> return it
    - Else call fetch_fn() -> cache -> return
    """
    if cache_path.exists() and cache_path.stat().st_size > min_bytes:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and not any(k in cached for k in ["Error Message", "Note", "Information"]):
                return cached
        except Exception:
            pass

    data = fetch_fn()
    try:
        save_json(cache_path, data)
    except Exception:
        pass
    return data


def fetch_av_json(function: str, api_key: str, symbol: Optional[str] = None, **kwargs: Any) -> dict:
    params = {"function": function, "apikey": api_key}
    if symbol is not None:
        params["symbol"] = symbol
    params.update(kwargs)

    r = requests.get(CFG.av_base, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()

    if "Error Message" in data:
        raise RuntimeError(data["Error Message"])
    if "Note" in data:
        raise RuntimeError(data["Note"])
    if "Information" in data:
        raise RuntimeError(data["Information"])
    return data


def av_get(
    function: str,
    api_key: str,
    symbol: Optional[str] = None,
    raw_dir: Path | None = None,
    sleep_seconds: int = 12,
    **kwargs: Any,
) -> dict:
    """
    Cache-first Alpha Vantage getter (your notebook logic).
    """
    ensure_dirs(CFG)
    raw_dir = raw_dir or CFG.raw_dir
    sym = symbol if symbol is not None else "GLOBAL"
    cache_path = raw_dir / f"{sym}_{function}.json"

    def _do_fetch() -> dict:
        return fetch_av_json(function=function, api_key=api_key, symbol=symbol, **kwargs)

    # cache first
    data = load_or_fetch_av(cache_path, _do_fetch)

    # only sleep if we actually fetched live (heuristic: cache missing or too small)
    # (safe + keeps notebook-style rate-limit handling)
    if not cache_path.exists() or cache_path.stat().st_size <= 200:
        time.sleep(sleep_seconds)

    return data


def fetch_annual_statements(symbol: str, api_key: str) -> dict[str, Path]:
    """
    Download (or reuse cached) annual Income/BS/CF jsons.
    Returns dict of file paths.
    """
    ensure_dirs(CFG)
    functions = {
        "income_statement": "INCOME_STATEMENT",
        "balance_sheet": "BALANCE_SHEET",
        "cash_flow": "CASH_FLOW",
    }

    paths: dict[str, Path] = {}
    for name, fn in functions.items():
        out_path = CFG.raw_dir / f"{symbol}_{name}.json"
        if out_path.exists() and out_path.stat().st_size > 200:
            paths[name] = out_path
            continue

        data = av_get(fn, api_key=api_key, symbol=symbol)
        save_json(out_path, data)
        paths[name] = out_path

    return paths
