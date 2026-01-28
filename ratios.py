from __future__ import annotations

import numpy as np
import pandas as pd


def compute_ratio_tables(merged_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Matches your notebook ratio logic:
      - profitability: gross/operating/net margins, ROA, ROE
      - leverage/liquidity: debt-to-equity, current ratio, interest coverage
      - growth: revenue/net income/fcf YoY
      - efficiency: asset turnover, fcf margin, cfo/net income
    """
    df = merged_df.copy().sort_values("fiscal_year").reset_index(drop=True)

    # averages for ROA/ROE & turnover
    df["avg_assets"] = (df["total_assets"] + df["total_assets"].shift(1)) / 2
    df["avg_equity"] = (df["total_shareholder_equity"] + df["total_shareholder_equity"].shift(1)) / 2

    # profitability
    df["gross_margin"] = df["gross_profit"] / df["revenue"]
    df["operating_margin"] = df["operating_income"] / df["revenue"]
    df["net_margin"] = df["net_income"] / df["revenue"]
    df["roa"] = df["net_income"] / df["avg_assets"]
    df["roe"] = df["net_income"] / df["avg_equity"]

    metrics_cols = ["gross_margin", "operating_margin", "net_margin", "roa", "roe"]
    metrics_table = (
        df.set_index("fiscal_year")[metrics_cols]
        .T.rename(
            index={
                "gross_margin": "Gross margin",
                "operating_margin": "Operating margin",
                "net_margin": "Net margin",
                "roa": "ROA",
                "roe": "ROE",
            }
        )
    )

    # leverage / liquidity
    df["debt_total"] = df[["long_term_debt", "short_term_debt"]].sum(axis=1, min_count=1)
    df["debt_to_equity"] = df["debt_total"] / df["total_shareholder_equity"]
    df["current_ratio"] = df["current_assets"] / df["current_liabilities"]

    # protect against 0/NA interest expense
    ie = df["interest_expense"].replace(0, np.nan)
    df["interest_coverage"] = df["operating_income"] / ie

    leverage_cols = ["debt_to_equity", "current_ratio", "interest_coverage"]
    leverage_table = (
        df.set_index("fiscal_year")[leverage_cols]
        .T.rename(
            index={
                "debt_to_equity": "Debt-to-Equity",
                "current_ratio": "Current Ratio",
                "interest_coverage": "Interest Coverage",
            }
        )
    )

    # growth (YoY)
    df_calc = df.copy()
    df_calc["revenue_yoy"] = df_calc["revenue"].pct_change()
    df_calc["net_income_yoy"] = df_calc["net_income"].pct_change()
    df_calc["fcf_yoy"] = df_calc["free_cash_flow"].pct_change()

    growth_cols = ["revenue_yoy", "net_income_yoy", "fcf_yoy"]
    growth_table = (
        df_calc.set_index("fiscal_year")[growth_cols]
        .T.rename(
            index={
                "revenue_yoy": "Revenue YoY Growth",
                "net_income_yoy": "Net Income YoY Growth",
                "fcf_yoy": "FCF YoY Growth",
            }
        )
    )

    # efficiency
    df_calc["asset_turnover"] = df_calc["revenue"] / df_calc["avg_assets"]
    df_calc["fcf_margin"] = df_calc["free_cash_flow"] / df_calc["revenue"]
    df_calc["cfo_to_net_income"] = df_calc["operating_cash_flow"] / df_calc["net_income"]

    efficiency_cols = ["asset_turnover", "fcf_margin", "cfo_to_net_income"]
    efficiency_table = (
        df_calc.set_index("fiscal_year")[efficiency_cols]
        .T.rename(
            index={
                "asset_turnover": "Asset Turnover",
                "fcf_margin": "FCF Margin",
                "cfo_to_net_income": "CFO / Net Income",
            }
        )
    )

    return {
        "df_calc": df_calc,
        "metrics_table": metrics_table,
        "leverage_table": leverage_table,
        "growth_table": growth_table,
        "efficiency_table": efficiency_table,
    }
