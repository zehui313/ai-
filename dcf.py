from __future__ import annotations

import requests
import numpy as np
import pandas as pd

from config import CFG
from data_fetcher import av_get
from multiples import marketcap_av


def risk_free_rate_us() -> float:
    """
    US 10Y Treasury from FRED (DGS10). Returns decimal.
    Falls back to 4% if fetch fails.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    try:
        df = pd.read_csv(url)
        df["DGS10"] = pd.to_numeric(df["DGS10"], errors="coerce")
        rf = df["DGS10"].dropna().iloc[-1]
        return float(rf) / 100.0
    except Exception:
        return 0.04


def beta_from_av(symbol: str, api_key: str) -> float:
    ov = av_get("OVERVIEW", api_key=api_key, symbol=symbol)
    try:
        return float(ov.get("Beta", np.nan))
    except Exception:
        return np.nan


def _download(url: str) -> bytes | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _erp_from_ctryprem_xlsx(path) -> float:
    xls = pd.read_excel(path, sheet_name=0)
    cols = {str(c).strip().lower(): c for c in xls.columns}
    col_found = None
    for low, orig in cols.items():
        if ("mature" in low) and ("premium" in low):
            col_found = orig
            break
    if col_found is None:
        raise RuntimeError("Cannot find Mature Market premium column.")
    ser = pd.to_numeric(xls[col_found], errors="coerce").dropna()
    return float(ser.median()) / 100.0


def _erp_from_histimpl_xls(path) -> float:
    xls = pd.read_excel(path, sheet_name=0)
    col = None
    for c in xls.columns:
        low = str(c).lower()
        if "erp" in low or ("implied" in low and "premium" in low):
            col = c
            break
    if col is None:
        raise RuntimeError("Cannot find ERP column in histimpl.")
    ser = pd.to_numeric(xls[col], errors="coerce").dropna()
    return float(ser.iloc[-1]) / 100.0


def erp_us_auto(cache_dir=None) -> tuple[float, str]:
    """
    Notebook-style “auto ERP” with Damodaran fallback. If all fails -> 5%.
    """
    cache_dir = cache_dir or CFG.raw_dir
    ctry_cache = cache_dir / "damodaran_ctryprem.xlsx"
    hist_cache = cache_dir / "damodaran_histimpl.xls"

    urls = [
        ("ctryprem", "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.xlsx", ctry_cache),
        ("histimpl", "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histimpl.xls", hist_cache),
    ]

    # try download then parse
    for tag, url, path in urls:
        content = _download(url)
        if content:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                if tag == "ctryprem":
                    return _erp_from_ctryprem_xlsx(path), "Damodaran ctryprem.xlsx (downloaded)"
                else:
                    return _erp_from_histimpl_xls(path), "Damodaran histimpl.xls (downloaded)"
            except Exception:
                pass

    # try cached
    try:
        if ctry_cache.exists() and ctry_cache.stat().st_size > 10_000:
            return _erp_from_ctryprem_xlsx(ctry_cache), "Damodaran ctryprem.xlsx (cached)"
    except Exception:
        pass

    try:
        if hist_cache.exists() and hist_cache.stat().st_size > 5_000:
            return _erp_from_histimpl_xls(hist_cache), "Damodaran histimpl.xls (cached)"
    except Exception:
        pass

    return 0.05, "Fallback default 5% (all external ERP fetch failed)"


def cost_of_debt_from_statements(is_view: pd.DataFrame, bs_view: pd.DataFrame, year: int) -> float:
    """
    Rd = |interest expense| / total debt
    (consistent with your notebook approach)
    """
    try:
        interest = float(is_view.loc["interest_expense", year])
        debt = float(bs_view.loc["long_term_debt", year] + bs_view.loc["short_term_debt", year])
    except Exception:
        return np.nan

    interest = abs(interest)
    if not np.isfinite(debt) or debt <= 0:
        return np.nan
    return interest / debt


def compute_wacc(
    symbol: str,
    api_key: str,
    base_year: int,
    is_view: pd.DataFrame,
    bs_view: pd.DataFrame,
    tax_rate: float,
) -> dict:
    rf = risk_free_rate_us()
    beta = beta_from_av(symbol, api_key)
    erp, erp_source = erp_us_auto()
    re = rf + beta * erp

    rd = cost_of_debt_from_statements(is_view, bs_view, base_year)

    # D is already in USD bn (because statements are scaled)
    try:
        D = float(bs_view.loc["long_term_debt", base_year] + bs_view.loc["short_term_debt", base_year])
    except Exception:
        D = np.nan

    # Equity from AV market cap (USD) -> USD bn
    E = float(marketcap_av(symbol, api_key)) / CFG.usd_bn

    V = D + E if np.isfinite(D) and np.isfinite(E) else np.nan
    wE = E / V if (np.isfinite(V) and V > 0) else np.nan
    wD = D / V if (np.isfinite(V) and V > 0) else np.nan

    wacc = wE * re + wD * rd * (1 - tax_rate) if np.isfinite(wE) and np.isfinite(wD) else np.nan

    return {
        "Risk-free rate (10Y)": rf,
        "Beta": beta,
        "ERP": erp,
        "ERP source": erp_source,
        "Cost of equity (Re)": re,
        "Cost of debt (Rd)": rd,
        "Tax rate": float(tax_rate),
        "Debt (D, USD bn)": float(D) if np.isfinite(D) else np.nan,
        "Equity (E, USD bn)": float(E) if np.isfinite(E) else np.nan,
        "wE": wE,
        "wD": wD,
        "WACC": wacc,
    }


def build_fcff_dcf(
    symbol: str,
    api_key: str,
    base_year: int,
    start_year: int,
    horizon: int,
    terminal_growth: float,
    is_view: pd.DataFrame,
    bs_view: pd.DataFrame,
    cf_view: pd.DataFrame,
) -> dict:
    """
    Fully matches your notebook DCF logic, but packaged as a function.
    """
    rev0 = float(is_view.loc["revenue", base_year])
    ebit0 = float(is_view.loc["operating_income", base_year])
    ebit_margin = ebit0 / rev0

    tax_rate = (is_view.loc["income_tax_expense"] / is_view.loc["income_before_tax"]).loc[base_year - 2 : base_year].median()
    tax_rate = float(np.clip(tax_rate, 0.05, 0.25))

    da_ratio = (cf_view.loc["depreciation_and_amortization"] / is_view.loc["revenue"]).loc[base_year - 2 : base_year].median()
    capex_ratio = (cf_view.loc["capex_outflow"] / is_view.loc["revenue"]).loc[base_year - 2 : base_year].median()

    nwc_level = (bs_view.loc["current_assets"] - bs_view.loc["current_liabilities"])
    nwc_ratio = (nwc_level / is_view.loc["revenue"]).loc[base_year - 2 : base_year].median()

    # revenue CAGR
    rev_start = float(is_view.loc["revenue", start_year])
    n = base_year - start_year
    rev_cagr = (rev0 / rev_start) ** (1 / n) - 1

    years_fwd = list(range(base_year + 1, base_year + 1 + horizon))
    revenue_forecast = pd.Series([rev0 * ((1 + rev_cagr) ** i) for i in range(1, horizon + 1)], index=years_fwd)

    # FCFF components
    ebit_f = revenue_forecast * ebit_margin
    nopat_f = ebit_f * (1 - tax_rate)

    da_f = revenue_forecast * float(da_ratio)
    capex_f = revenue_forecast * float(capex_ratio)

    nwc_level_f = revenue_forecast * float(nwc_ratio)
    nwc_base = float(nwc_level.loc[base_year])
    delta_nwc = nwc_level_f.diff()
    delta_nwc.iloc[0] = nwc_level_f.iloc[0] - nwc_base

    fcff_f = nopat_f + da_f - capex_f - delta_nwc

    fcff_tbl = pd.DataFrame(
        {
            "Revenue": revenue_forecast,
            "EBIT": ebit_f,
            "NOPAT": nopat_f,
            "D&A": da_f,
            "CapEx": capex_f,
            "ΔNWC": delta_nwc,
            "FCFF": fcff_f,
        }
    )

    # WACC
    wacc_out = compute_wacc(symbol, api_key, base_year, is_view, bs_view, tax_rate)
    wacc = float(wacc_out["WACC"])

    # PV + TV
    fcffs = fcff_f.astype(float).to_numpy()
    g = float(terminal_growth)
    tv = fcffs[-1] * (1 + g) / (wacc - g)
    pv_fcff = sum([fcffs[i] / (1 + wacc) ** (i + 1) for i in range(horizon)])
    pv_tv = tv / (1 + wacc) ** horizon
    EV = pv_fcff + pv_tv

    # Equity value: EV - net debt
    debt = float(bs_view.loc["long_term_debt", base_year] + bs_view.loc["short_term_debt", base_year])
    cash = float(bs_view.loc["cash_and_cash_equivalents", base_year])
    equity = EV - (debt - cash)

    # shares + implied price (from AV overview)
    ov = av_get("OVERVIEW", api_key=api_key, symbol=symbol)
    shares = float(ov.get("SharesOutstanding", np.nan)) / CFG.usd_bn  # bn shares
    implied_price = (equity * CFG.usd_bn) / (shares * CFG.usd_bn) if (shares and shares > 0) else np.nan

    return {
        "assumptions": {
            "base_year": base_year,
            "start_year": start_year,
            "horizon": horizon,
            "rev_cagr": float(rev_cagr),
            "ebit_margin": float(ebit_margin),
            "tax_rate": float(tax_rate),
            "da_ratio": float(da_ratio),
            "capex_ratio": float(capex_ratio),
            "nwc_ratio": float(nwc_ratio),
            "terminal_growth": g,
        },
        "wacc": wacc_out,
        "fcff_table": fcff_tbl,
        "valuation": {
            "PV_FCFF": float(pv_fcff),
            "PV_TV": float(pv_tv),
            "EV": float(EV),
            "Debt": float(debt),
            "Cash": float(cash),
            "Equity": float(equity),
            "Shares_bn": float(shares),
            "ImpliedPrice": float(implied_price),
        },
    }
