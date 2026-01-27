# NVDA Fundamental Agent (Notebook → Modular Python)

This repo modularizes the original Jupyter notebook into a clean pipeline:

- **data_fetcher.py**: Alpha Vantage cache-first downloader
- **statements.py**: standardize Income/BS/CF and build merged table + views
- **ratios.py**: ratio tables (profitability, leverage/liquidity, growth, efficiency)
- **multiples.py**: TTM peer multiples (P/E, EV/EBITDA, EV/Sales) + optional benchmarks
- **dcf.py**: FCFF-based DCF with auto WACC (FRED rf + AV beta + Damodaran ERP + statements Rd)
- **visualization.py**: figures for ratios and multiples
- **llm_report.py**: generate investment memo via **Ollama** (llama3)
- **main.py**: orchestrates the full pipeline and writes outputs
- **run_demo.py**: one-command demo runner

## Setup

1) Install dependencies
```bash
pip install -r requirements.txt

