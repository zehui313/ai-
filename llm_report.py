from __future__ import annotations

import subprocess
from pathlib import Path
import textwrap

import pandas as pd

from config import CFG, ensure_dirs


def _df_to_md(df: pd.DataFrame | None, title: str, max_rows: int = 50) -> str:
    if df is None:
        return f"### {title}\n(N/A)\n"
    d = df.copy()
    if d.shape[0] > max_rows:
        d = d.head(max_rows)

    # to_markdown requires tabulate; fallback if missing
    try:
        body = d.to_markdown()
    except Exception:
        body = d.to_string()

    return f"### {title}\n{body}\n"


def col_trend_summary(table: pd.DataFrame, row_name: str, label: str, years=None, pct=True) -> str:
    s = table.loc[row_name].dropna()
    if years is not None:
        s = s.loc[[y for y in years if y in s.index]]
    if s.empty:
        return f"- {label}: N/A"

    y0, y1 = int(s.index[0]), int(s.index[-1])
    v0, v1 = float(s.iloc[0]), float(s.iloc[-1])
    vmin, ymin = float(s.min()), int(s.idxmin())
    vmax, ymax = float(s.max()), int(s.idxmax())

    if pct:
        fmt = lambda x: f"{x:.2%}"
    else:
        fmt = lambda x: f"{x:.2f}"

    return (
        f"- {label}: {fmt(v0)} ({y0}) → {fmt(v1)} ({y1}); "
        f"min {fmt(vmin)} ({ymin}), max {fmt(vmax)} ({ymax})."
    )


def build_prompt(
    symbol: str,
    ratio_tables: dict[str, pd.DataFrame],
    multiples: pd.DataFrame,
    dcf_out: dict,
) -> str:
    years = [2021, 2022, 2023, 2024, 2025]

    metrics = ratio_tables.get("metrics_table")
    lev = ratio_tables.get("leverage_table")
    gro = ratio_tables.get("growth_table")
    eff = ratio_tables.get("efficiency_table")

    ratio_facts = []
    if metrics is not None:
        ratio_facts.append("## Profitability")
        ratio_facts.append(col_trend_summary(metrics, "Gross margin", "Gross margin", years=years, pct=True))
        ratio_facts.append(col_trend_summary(metrics, "Operating margin", "Operating margin", years=years, pct=True))
        ratio_facts.append(col_trend_summary(metrics, "Net margin", "Net margin", years=years, pct=True))
        ratio_facts.append(col_trend_summary(metrics, "ROA", "ROA", years=years, pct=True))
        ratio_facts.append(col_trend_summary(metrics, "ROE", "ROE", years=years, pct=True))

    if lev is not None:
        ratio_facts.append("\n## Leverage & Liquidity")
        ratio_facts.append(col_trend_summary(lev, "Debt-to-Equity", "Debt-to-Equity", years=years, pct=False))
        ratio_facts.append(col_trend_summary(lev, "Current Ratio", "Current ratio", years=years, pct=False))
        ratio_facts.append(col_trend_summary(lev, "Interest Coverage", "Interest coverage", years=years, pct=False))

    if gro is not None:
        ratio_facts.append("\n## Growth")
        ratio_facts.append(col_trend_summary(gro, "Revenue YoY Growth", "Revenue YoY growth", years=years, pct=True))
        ratio_facts.append(col_trend_summary(gro, "Net Income YoY Growth", "Net income YoY growth", years=years, pct=True))
        ratio_facts.append(col_trend_summary(gro, "FCF YoY Growth", "FCF YoY growth", years=years, pct=True))

    if eff is not None:
        ratio_facts.append("\n## Efficiency & Cash Conversion")
        ratio_facts.append(col_trend_summary(eff, "Asset Turnover", "Asset turnover", years=years, pct=False))
        ratio_facts.append(col_trend_summary(eff, "FCF Margin", "FCF margin", years=years, pct=True))
        ratio_facts.append(col_trend_summary(eff, "CFO / Net Income", "CFO / Net income", years=years, pct=False))

    ratio_facts_text = "\n".join(ratio_facts)

    multiples_text = _df_to_md(multiples, "Multiples (TTM): P/E, EV/EBITDA, EV/Sales")
    dcf_inputs_text = textwrap.dedent(
        f"""
        ### DCF Assumptions
        {dcf_out.get("assumptions")}

        ### WACC
        {dcf_out.get("wacc")}

        ### Valuation
        {dcf_out.get("valuation")}
        """
    ).strip()

    prompt = f"""
You are a senior equity research analyst writing an investment memo for {symbol}.

IMPORTANT:
- This memo is NOT a data summary.
- Your job is to INTERPRET what the computed outputs imply for valuation.
- Use ONLY the provided data. Do NOT introduce new numbers or assumptions.
- If interpretation is uncertain, state uncertainty explicitly.

STRUCTURE (use headings):
1) Business performance & profitability (ratios)
2) Financial risk & liquidity
3) Growth dynamics
4) Multiples valuation and peer comparison
5) DCF valuation and intrinsic value assessment
6) Recommendation and key risks
7) Data sources

ANALYSIS RULES:
- In EACH ratio subsection: cite at least 2 exact datapoints (year + value).
- Explain what changed, why it likely changed, and whether it appears structural or cyclical.
- Explicitly connect ratio behavior to valuation implications (pricing power, risk, sustainability).

=====================
RATIO TABLE FACTS (pre-computed)
=====================
{ratio_facts_text}

=====================
MULTIPLES PEER COMPARISON (pre-computed)
=====================
{multiples_text}

=====================
DCF INPUTS AND OUTPUTS (pre-computed)
=====================
{dcf_inputs_text}
""".strip()

    return prompt


def generate_investment_memo(
    symbol: str,
    ratio_tables: dict[str, pd.DataFrame],
    multiples: pd.DataFrame,
    dcf_out: dict,
) -> Path:
    ensure_dirs(CFG)

    prompt = build_prompt(symbol, ratio_tables, multiples, dcf_out)

    # Always save prompt for reproducibility
    CFG.prompt_path.write_text(prompt, encoding="utf-8")

    # Try Ollama (matches your notebook)
    try:
        result = subprocess.run(
            ["ollama", "run", CFG.ollama_model],
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
        memo_text = (result.stdout or "").strip()
        if not memo_text:
            raise RuntimeError(result.stderr or "Empty Ollama output")
        CFG.memo_path.write_text(memo_text, encoding="utf-8")
        return CFG.memo_path
    except Exception:
        # fallback: write a minimal memo that points to prompt
        fallback = f"""# Investment Memo (Fallback)

Ollama was not available. The prompt has been saved to:
- {CFG.prompt_path}

You can generate the memo by running:
ollama run {CFG.ollama_model} < {CFG.prompt_path}
"""
        CFG.memo_path.write_text(fallback, encoding="utf-8")
        return CFG.memo_path
