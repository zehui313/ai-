from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from config import CFG


def plot_metric_ax(ax, df, col, title, is_percent=False):
    ax.plot(df.index, df[col])
    ax.set_title(title)
    if is_percent:
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))


def save_fig(fig, name: str) -> Path:
    out = CFG.figs_dir / name
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_ratio_panels(df_calc: pd.DataFrame) -> list[Path]:
    """
    Replaces your notebook multi-panel plots for:
      - profitability (gross/op/net/roa/roe)
      - leverage/liquidity (debt_to_equity/current_ratio/interest_coverage)
      - growth (revenue_yoy/net_income_yoy/fcf_yoy)
      - efficiency (asset_turnover/fcf_margin/cfo_to_net_income)
    """
    outs: list[Path] = []
    d = df_calc.set_index("fiscal_year").copy()

    # 1) profitability (2x3)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), constrained_layout=True)
    axes = axes.flatten()
    metrics_5 = [
        ("gross_margin", "Gross Margin", True),
        ("operating_margin", "Operating Margin", True),
        ("net_margin", "Net Margin", True),
        ("roa", "ROA", True),
        ("roe", "ROE", True),
    ]
    for ax, (col, title, is_pct) in zip(axes, metrics_5):
        plot_metric_ax(ax=ax, df=d, col=col, title=f"NVDA {title} (FY{d.index.min()}–FY{d.index.max()})", is_percent=is_pct)

    # last subplot empty
    fig.delaxes(axes[-1])
    outs.append(save_fig(fig, "ratios_profitability.png"))

    # 2) leverage/liquidity (2x2 -> 3 charts)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), constrained_layout=True)
    plot_metric_ax(axes[0, 0], d, "debt_to_equity", "NVDA Debt-to-Equity", is_percent=False)
    plot_metric_ax(axes[0, 1], d, "current_ratio", "NVDA Current Ratio", is_percent=False)
    plot_metric_ax(axes[1, 0], d, "interest_coverage", "NVDA Interest Coverage", is_percent=False)
    fig.delaxes(axes[1, 1])
    outs.append(save_fig(fig, "ratios_leverage_liquidity.png"))

    # 3) growth (2x2 -> 3 charts)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), constrained_layout=True)
    plot_metric_ax(axes[0, 0], d, "revenue_yoy", "NVDA Revenue YoY Growth", is_percent=True)
    plot_metric_ax(axes[0, 1], d, "net_income_yoy", "NVDA Net Income YoY Growth", is_percent=True)
    plot_metric_ax(axes[1, 0], d, "fcf_yoy", "NVDA FCF YoY Growth", is_percent=True)
    fig.delaxes(axes[1, 1])
    outs.append(save_fig(fig, "ratios_growth.png"))

    # 4) efficiency (2x2 -> 3 charts)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), constrained_layout=True)
    plot_metric_ax(axes[0, 0], d, "asset_turnover", "NVDA Asset Turnover", is_percent=False)
    plot_metric_ax(axes[0, 1], d, "fcf_margin", "NVDA FCF Margin", is_percent=True)
    plot_metric_ax(axes[1, 0], d, "cfo_to_net_income", "NVDA CFO / Net Income", is_percent=False)
    fig.delaxes(axes[1, 1])
    outs.append(save_fig(fig, "ratios_efficiency.png"))

    return outs


def plot_multiples_figures(multiples: pd.DataFrame) -> list[Path]:
    """
    Matches your notebook:
      - bar EV/EBITDA
      - bar EV/Sales (with custom order)
      - scatter EV/EBITDA vs EV/Sales
      - scatter EV/Sales vs EBITDA Margin (we put placeholder hook; pass margins separately if needed)
    """
    outs: list[Path] = []

    # bar EV/EBITDA
    fig = plt.figure()
    ax = multiples["EV/EBITDA (TTM)"].sort_values().plot(kind="bar", title=f"EV/EBITDA (TTM) — as of {CFG.asof}", rot=0)
    ax.set_ylabel("x")
    outs.append(save_fig(fig, "multiples_ev_ebitda_bar.png"))

    # bar EV/Sales with order (same as your notebook)
    order = ["NVDA", "ADI", "QCOM", "TXN", "Semiconductor Avg", "Market Avg (S&P500)"]
    fig = plt.figure()
    ax = multiples.loc[[o for o in order if o in multiples.index], "EV/Sales (TTM)"].plot(
        kind="bar", title=f"EV/Sales (TTM) — as of {CFG.asof}", rot=0
    )
    ax.set_ylabel("x")
    outs.append(save_fig(fig, "multiples_ev_sales_bar.png"))

    # scatter EV/EBITDA vs EV/Sales
    fig = plt.figure()
    x = multiples["EV/Sales (TTM)"]
    y = multiples["EV/EBITDA (TTM)"]
    plt.scatter(x, y)
    for name in multiples.index:
        plt.annotate(name, (x.loc[name], y.loc[name]))
    plt.title(f"EV/EBITDA vs EV/Sales (TTM) — as of {CFG.asof}")
    plt.xlabel("EV/Sales (x)")
    plt.ylabel("EV/EBITDA (x)")
    outs.append(save_fig(fig, "multiples_scatter_ev_ebitda_vs_ev_sales.png"))

    return outs
