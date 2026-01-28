from __future__ import annotations

from pathlib import Path
import pandas as pd

from config import CFG, ensure_dirs, load_api_key
from data_fetcher import fetch_annual_statements
from statements import build_statement_tables, to_view
from ratios import compute_ratio_tables
from multiples import build_multiples_input_table, compute_multiples_from_input, add_benchmarks
from dcf import build_fcff_dcf
from visualization import plot_ratio_panels, plot_multiples_figures
from llm_report import generate_investment_memo


def _write_table(df: pd.DataFrame, name: str) -> Path:
    ensure_dirs(CFG)
    out_csv = CFG.out_dir / f"{name}.csv"
    df.to_csv(out_csv, index=True)
    return out_csv


def run_pipeline() -> dict:
    ensure_dirs(CFG)
    api_key = load_api_key()

    # 1) Annual statements -> standardized tables + views
    paths = fetch_annual_statements(CFG.symbol, api_key)
    is_df, bs_df, cf_df, merged_df = build_statement_tables(paths)

    is_view = to_view(is_df)
    bs_view = to_view(bs_df)
    cf_view = to_view(cf_df)

    # 2) Ratios
    ratio_out = compute_ratio_tables(merged_df)

    # 3) Multiples (TTM) + benchmarks
    multiples_input = build_multiples_input_table(api_key=api_key)
    multiples = compute_multiples_from_input(multiples_input)
    multiples = add_benchmarks(multiples)

    # 4) DCF
    dcf_out = build_fcff_dcf(
        symbol=CFG.symbol,
        api_key=api_key,
        base_year=CFG.base_year,
        start_year=CFG.start_year_for_cagr,
        horizon=CFG.horizon,
        terminal_growth=CFG.terminal_growth,
        is_view=is_view,
        bs_view=bs_view,
        cf_view=cf_view,
    )

    # 5) Save outputs
    _write_table(is_view, "income_view")
    _write_table(bs_view, "balance_view")
    _write_table(cf_view, "cashflow_view")
    _write_table(ratio_out["metrics_table"], "ratios_profitability")
    _write_table(ratio_out["leverage_table"], "ratios_leverage_liquidity")
    _write_table(ratio_out["growth_table"], "ratios_growth")
    _write_table(ratio_out["efficiency_table"], "ratios_efficiency")
    _write_table(multiples_input, "multiples_inputs")
    _write_table(multiples, "multiples_ttm")
    _write_table(dcf_out["fcff_table"], "dcf_fcff_table")

    # 6) Figures
    fig_paths = []
    fig_paths += plot_ratio_panels(ratio_out["df_calc"])
    fig_paths += plot_multiples_figures(multiples)

    # 7) LLM memo (Ollama)
    memo_path = generate_investment_memo(CFG.symbol, ratio_out, multiples, dcf_out)

    return {
        "is_view": is_view,
        "bs_view": bs_view,
        "cf_view": cf_view,
        "ratios": ratio_out,
        "multiples_input": multiples_input,
        "multiples": multiples,
        "dcf": dcf_out,
        "figures": fig_paths,
        "memo_path": memo_path,
    }
