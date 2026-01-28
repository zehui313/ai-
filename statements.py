from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import CFG


def load_reports(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    reps = data.get("annualReports", [])
    if not reps:
        raise RuntimeError(f"No annualReports found in {path}")
    return reps


def year_from_fiscal_date(s: str) -> int:
    return int(s[:4])


def to_int(x):
    try:
        return int(float(x))
    except Exception:
        return pd.NA


def standardize_income(path: Path) -> pd.DataFrame:
    reps = load_reports(path)
    rows = []
    years = set(CFG.years)
    for r in reps:
        y = year_from_fiscal_date(r["fiscalDateEnding"])
        if y not in years:
            continue
        rows.append(
            {
                "fiscal_year": y,
                "fiscal_date_ending": r["fiscalDateEnding"],
                "revenue": to_int(r.get("totalRevenue")),
                "cogs": to_int(r.get("costOfRevenue")),
                "gross_profit": to_int(r.get("grossProfit")),
                "operating_income": to_int(r.get("operatingIncome")),
                "net_income": to_int(r.get("netIncome")),
                "interest_expense": to_int(r.get("interestExpense")),
                "income_before_tax": to_int(r.get("incomeBeforeTax")),
                "income_tax_expense": to_int(r.get("incomeTaxExpense")),
            }
        )
    return pd.DataFrame(rows).sort_values("fiscal_year").reset_index(drop=True)


def standardize_balance(path: Path) -> pd.DataFrame:
    reps = load_reports(path)
    rows = []
    years = set(CFG.years)
    for r in reps:
        y = year_from_fiscal_date(r["fiscalDateEnding"])
        if y not in years:
            continue
        rows.append(
            {
                "fiscal_year": y,
                "fiscal_date_ending": r["fiscalDateEnding"],
                "total_assets": to_int(r.get("totalAssets")),
                "total_liabilities": to_int(r.get("totalLiabilities")),
                "total_shareholder_equity": to_int(r.get("totalShareholderEquity")),
                "cash_and_cash_equivalents": to_int(r.get("cashAndCashEquivalentsAtCarryingValue")),
                "current_assets": to_int(r.get("totalCurrentAssets")),
                "current_liabilities": to_int(r.get("totalCurrentLiabilities")),
                "long_term_debt": to_int(r.get("longTermDebt")),
                "short_term_debt": to_int(r.get("shortTermDebt")),
                "short_term_investments": to_int(r.get("shortTermInvestments")),
            }
        )
    return pd.DataFrame(rows).sort_values("fiscal_year").reset_index(drop=True)


def standardize_cashflow(path: Path) -> pd.DataFrame:
    reps = load_reports(path)
    rows = []
    years = set(CFG.years)

    for r in reps:
        y = year_from_fiscal_date(r["fiscalDateEnding"])
        if y not in years:
            continue

        cfo = to_int(r.get("operatingCashflow"))
        capex = to_int(r.get("capitalExpenditures"))

        # notebook逻辑：AV capex 常为负数；转成“正的现金流出”
        capex_outflow = abs(capex) if pd.notna(capex) else pd.NA

        da = to_int(r.get("depreciationDepletionAndAmortization"))

        # FCF = CFO - Capex(outflow)
        if pd.notna(cfo) and pd.notna(capex_outflow):
            fcf = cfo - capex_outflow
        else:
            fcf = pd.NA

        rows.append(
            {
                "fiscal_year": y,
                "fiscal_date_ending": r["fiscalDateEnding"],
                "operating_cash_flow": cfo,
                "capex": capex,
                "capex_outflow": capex_outflow,
                "free_cash_flow": fcf,
                "depreciation_and_amortization": da,
            }
        )

    return pd.DataFrame(rows).sort_values("fiscal_year").reset_index(drop=True)


def to_billions_inplace(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce") / CFG.usd_bn


def build_statement_tables(paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      - is_df, bs_df, cf_df: standardized annual tables (USD bn)
      - merged_df: inner-joined by fiscal_year (USD bn)
    """
    is_df = standardize_income(paths["income_statement"])
    bs_df = standardize_balance(paths["balance_sheet"])
    cf_df = standardize_cashflow(paths["cash_flow"])

    income_items = [
        "revenue", "cogs", "gross_profit", "operating_income", "net_income",
        "interest_expense", "income_before_tax", "income_tax_expense",
    ]
    balance_items = [
        "total_assets", "total_liabilities", "total_shareholder_equity",
        "cash_and_cash_equivalents", "current_assets", "current_liabilities",
        "long_term_debt", "short_term_debt", "short_term_investments",
    ]
    cashflow_items = [
        "operating_cash_flow", "capex", "capex_outflow",
        "free_cash_flow", "depreciation_and_amortization",
    ]

    to_billions_inplace(is_df, income_items)
    to_billions_inplace(bs_df, balance_items)
    to_billions_inplace(cf_df, cashflow_items)

    merged = (
        is_df.merge(bs_df, on="fiscal_year", how="inner", suffixes=("", "_bs"))
        .merge(cf_df, on="fiscal_year", how="inner", suffixes=("", "_cf"))
        .sort_values("fiscal_year")
        .reset_index(drop=True)
    )

    return is_df, bs_df, cf_df, merged


def to_view(df: pd.DataFrame, index_col: str = "fiscal_year") -> pd.DataFrame:
    """
    Convert standardized wide table to your notebook style:
      rows = metric, cols = fiscal_year
    """
    d = df.copy().set_index(index_col)
    if "fiscal_date_ending" in d.columns:
        d = d.drop(columns=["fiscal_date_ending"])
    return d.T
