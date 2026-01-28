from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    # Core tickers
    symbol: str = "NVDA"
    peer_tickers: tuple[str, ...] = ("NVDA", "ADI", "QCOM", "TXN")

    # Time
    years: tuple[int, ...] = (2020, 2021, 2022, 2023, 2024, 2025)
    base_year: int = 2025
    start_year_for_cagr: int = 2021
    horizon: int = 5

    # Multiples as-of (pick last 4 quarters <= ASOF)
    asof: str = "2025-01-31"

    # DCF
    terminal_growth: float = 0.045  # g

    # Optional benchmark multiples (from your notebook)
    bench_semiconductor_avg: tuple[float, float, float] = (37.29, 42.70, 15.70)  # P/E, EV/EBITDA, EV/Sales
    bench_market_avg_sp500: tuple[float, float, float] = (27.66, 23.95, 3.97)

    # Data/Cache dirs
    av_base: str = "https://www.alphavantage.co/query"
    raw_dir: Path = Path("data_raw/alphavantage")
    out_dir: Path = Path("outputs")
    figs_dir: Path = Path("outputs/figures")

    # Units
    usd_bn: float = 1e9

    # LLM / Memo
    ollama_model: str = "llama3:latest"
    memo_path: Path = Path("outputs/investment_memo.md")
    prompt_path: Path = Path("outputs/investment_memo_prompt.txt")


def ensure_dirs(cfg: Config) -> None:
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    cfg.figs_dir.mkdir(parents=True, exist_ok=True)


def load_api_key(env_path: str = "secrets.env") -> str:
    """
    Load ALPHAVANTAGE_API_KEY from secrets.env or system environment.
    """
    if Path(env_path).exists():
        load_dotenv(env_path)
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing ALPHAVANTAGE_API_KEY (set env var or create secrets.env)")
    return api_key


CFG = Config()
