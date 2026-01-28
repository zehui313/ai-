from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import CFG
from data_fetcher import av_get


def to_float(x):
    try:
        if x is None:
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def parse_date(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def pick_last_quarters(reports: list[dict], asof: pd.Timestamp, n: int = 4) -> list[dict]:
    rows = []
    for r in reports:
        dt = parse_date(r["fiscalDateEnding"])
        if dt <= asof:
            rows.append((dt, r))
    rows.sort(key=lambda x: x[0])
    return [r for _, r in rows[-n:]] if len(rows) >= n else []


def pick_latest_report(reports: list[dict], asof: pd.Timestamp) -> dict | None:
    rows = []
    for r in reports:
        dt = parse_date(r["fiscalDateEnding"])
        if dt <= asof:
            rows.append((dt, r))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])
    return rows[-1][1]


def av_overview(symbol: str, api_key: str) -> dict:
    return av_get("OVERVIEW", api_key=api_key, symbol=symbol)


def shares_outstanding_av(symbol: str, api_key: str) -> float:
    ov = av_overview(symbol, api_key)
    return to_float(ov.get("SharesOutstanding"))


def shares_outstanding_bn_from_av(symbol: str, api_key: str) -> float:
    sh = shares_outstanding_av(symbol, api_key)
    return sh / CFG.usd_bn if pd.notna(sh) else np.nan


def marketcap_av(symbol: str, api_key: str) -> float:
    ov = av_overview(symbol, api_key)
    return to_float(ov.get("MarketCapitalization"))


def marketcap_from_av(symbol: str, api_key: str) -> float:
    # alias (some notebook versions used this name)
    return marketcap_av(symbol, api_key)


def av_ttm_income_cash_balance(symbol: str, asof: pd.Timestamp, api_key: str) -> dict[str, Any]:
    """
    Your notebook TTM logic from quarterlyReports:
      - Revenue_TTM
      - NetIncome_TTM
      - EBITDA_TTM = EBIT_TTM + DA_TTM
      - Cash + TotalDebt from latest quarterly BS
    """
    inc = av_get("INCOME_STATEMENT", api_key=api_key, symbol=symbol)
    cf = av_get("CASH_FLOW", api_key=api_key, symbol=symbol)
    bs = av_get("BALANCE_SHEET", api_key=api_key, symbol=symbol)

    q_inc = inc.get("quarterlyReports", []) or []
    q_cf = cf.get("quarterlyReports", []) or []
    q_bs = bs.get("quarterlyReports", []) or []

    last4_inc = pick_last_quarters(q_inc, asof, n=4)
    last4_cf = pick_last_quarters(q_cf, asof, n=4)

    # income TTM
    if len(last4_inc) < 4:
        revenue_ttm = np.nan
        net_income_ttm = np.nan
        ebit_ttm = np.nan
        last_q_used = None
    else:
        revenue_ttm = sum(to_float(r.get("totalRevenue")) for r in last4_inc)
        net_income_ttm = sum(to_float(r.get("netIncome")) for r in last4_inc)

        # EBIT: try ebit first; fallback to operatingIncome
        ebit_vals = []
        for r in last4_inc:
            v = to_float(r.get("ebit"))
            if pd.isna(v):
                v = to_float(r.get("operatingIncome"))
            ebit_vals.append(v)
        ebit_ttm = np.nan if any(pd.isna(v) for v in ebit_vals) else float(np.sum(ebit_vals))
        last_q_used = last4_inc[-1]["fiscalDateEnding"]

    # DA TTM
    if len(last4_cf) < 4:
        da_ttm = np.nan
        last_q_cf_used = None
    else:
        da_keys = [
            "depreciationDepletionAndAmortization",
            "depreciationAndAmortization",
            "depreciation",
        ]
        da_vals = []
        for r in last4_cf:
            v = np.nan
            for k in da_keys:
                v = to_float(r.get(k))
                if pd.notna(v):
                    break
            da_vals.append(v)
        da_ttm = np.nan if any(pd.isna(v) for v in da_vals) else float(np.sum(da_vals))
        last_q_cf_used = last4_cf[-1]["fiscalDateEnding"]

    ebitda_ttm = (ebit_ttm + da_ttm) if (pd.notna(ebit_ttm) and pd.notna(da_ttm)) else np.nan

    # balance snapshot
    bs_last = pick_latest_report(q_bs, asof)
    if bs_last is None:
        cash = np.nan
        total_debt = np.nan
        bs_used = None
    else:
        bs_used = bs_last["fiscalDateEnding"]
        cash = to_float(bs_last.get("cashAndCashEquivalentsAtCarryingValue"))

        debt_lt = to_float(bs_last.get("longTermDebt"))
        debt_st = to_float(bs_last.get("shortLongTermDebtTotal"))  # ST + current portion
        debt_lt = 0.0 if pd.isna(debt_lt) else debt_lt
        debt_st = 0.0 if pd.isna(debt_st) else debt_st
        total_debt = debt_lt + debt_st

    return {
        "Revenue_TTM": revenue_ttm,
        "NetIncome_TTM": net_income_ttm,
        "EBITDA_TTM": ebitda_ttm,
        "Cash": cash,
        "TotalDebt": total_debt,
        "TTM_Income_LastQuarterUsed": last_q_used,
        "TTM_CF_LastQuarterUsed": last_q_cf_used,
        "Balance_LastQuarterUsed": bs_used,
    }


def extract_peer_row(symbol: str, asof: pd.Timestamp, api_key: str) -> pd.Series:
    av = av_ttm_income_cash_balance(symbol, asof, api_key)

    mkt = marketcap_av(symbol, api_key)  # USD
    sh = shares_outstanding_av(symbol, api_key)  # shares
    implied_px = (mkt / sh) if (pd.notna(mkt) and pd.notna(sh) and sh != 0) else np.nan

    USD_BN = CFG.usd_bn
    return pd.Series(
        {
            "ImpliedPrice (USD/share)": implied_px,
            "NetIncome_TTM (USD bn)": av["NetIncome_TTM"] / USD_BN if pd.notna(av["NetIncome_TTM"]) else np.nan,
            "SharesOutstanding (bn shares)": sh / USD_BN if pd.notna(sh) else np.nan,
            "MarketCap (USD bn)": mkt / USD_BN if pd.notna(mkt) else np.nan,
            "TotalDebt (USD bn)": av["TotalDebt"] / USD_BN if pd.notna(av["TotalDebt"]) else np.nan,
            "Cash (USD bn)": av["Cash"] / USD_BN if pd.notna(av["Cash"]) else np.nan,
            "EBITDA_TTM (USD bn)": av["EBITDA_TTM"] / USD_BN if pd.notna(av["EBITDA_TTM"]) else np.nan,
            "Revenue_TTM (USD bn)": av["Revenue_TTM"] / USD_BN if pd.notna(av["Revenue_TTM"]) else np.nan,
        },
        name=symbol,
    )


def build_multiples_input_table(api_key: str, tickers: list[str] | None = None, asof: str | None = None) -> pd.DataFrame:
    tickers = tickers or list(CFG.peer_tickers)
    asof_ts = pd.Timestamp(asof or CFG.asof)
    table = pd.concat([extract_peer_row(sym, asof_ts, api_key) for sym in tickers], axis=1)

    row_order = [
        "ImpliedPrice (USD/share)",
        "NetIncome_TTM (USD bn)",
        "SharesOutstanding (bn shares)",
        "MarketCap (USD bn)",
        "TotalDebt (USD bn)",
        "Cash (USD bn)",
        "EBITDA_TTM (USD bn)",
        "Revenue_TTM (USD bn)",
    ]
    return table.loc[row_order]


def compute_multiples_from_input(table: pd.DataFrame) -> pd.DataFrame:
    ev = table.loc["MarketCap (USD bn)"] + table.loc["TotalDebt (USD bn)"] - table.loc["Cash (USD bn)"]

    ni = table.loc["NetIncome_TTM (USD bn)"].replace(0, np.nan)
    ebitda = table.loc["EBITDA_TTM (USD bn)"].replace(0, np.nan)
    sales = table.loc["Revenue_TTM (USD bn)"].replace(0, np.nan)

    out = pd.DataFrame(
        {
            "P/E (TTM)": table.loc["MarketCap (USD bn)"] / ni,
            "EV/EBITDA (TTM)": ev / ebitda,
            "EV/Sales (TTM)": ev / sales,
        }
    )
    out.index.name = "Ticker"
    return out


def add_benchmarks(multiples: pd.DataFrame) -> pd.DataFrame:
    """
    Matches your notebook:
      multiples_ttm.loc["Semiconductor Avg"] = [37.29, 42.70, 15.70]
      multiples_ttm.loc["Market Avg (S&P500)"] = [27.66, 23.95, 3.97]
    """
    m = multiples.copy()
    m.loc["Semiconductor Avg"] = list(CFG.bench_semiconductor_avg)
    m.loc["Market Avg (S&P500)"] = list(CFG.bench_market_avg_sp500)
    return m
