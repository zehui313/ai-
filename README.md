# NVDA Fundamental Analyst Agent  
### AI-Driven Financial Analysis & Valuation System

This project implements a fully automated **AI-powered equity analysis pipeline** for **NVIDIA (NVDA)**.  
It integrates financial statement analysis, valuation modeling, data visualization, and AI-generated interpretation into one reproducible system.

---

## System Architecture
### Data → Statements → Ratios → Multiples → DCF → Figures → AI Memo

| Module | Function |
|--------|---------|
| `data_fetcher.py` | Downloads Alpha Vantage financial statements (cache-first) |
| `statements.py` | Standardizes Income / Balance Sheet / Cash Flow into USD billions |
| `ratios.py` | Computes profitability, leverage, efficiency, and growth ratios |
| `multiples.py` | Builds peer valuation multiples (P/E, EV/EBITDA, EV/Sales) |
| `dcf.py` | Revenue-driven FCFF DCF valuation with automatic WACC |
| `visualization.py` | Generates financial diagnostic figures |
| `llm_report.py` | Generates AI investment memo from analysis outputs |
| `main.py` | Orchestrates the full pipeline |
| `run_demo.py` | One-command execution |

---

## Financial Methods Implemented

### Financial Diagnostics
- Profitability trends (Margins, ROA, ROE)  
- Leverage & liquidity structure  
- Cash flow quality & efficiency  
- Growth dynamics  

### Relative Valuation (Multiples)
Peer comparison versus ADI, QCOM, TXN using:
- P/E  
- EV/EBITDA  
- EV/Sales  

### Intrinsic Valuation (DCF)

\[
FCFF = NOPAT + D\&A - CapEx - \Delta NWC
\]

WACC is automatically computed using:
- Risk-free rate (FRED 10Y Treasury)  
- Beta (Alpha Vantage)  
- Equity Risk Premium (Damodaran dataset)  
- Cost of debt from financial statements  

### AI Investment Memo
A Large Language Model interprets:
- Ratio dynamics  
- Peer positioning  
- FCFF drivers  
- Valuation implications  

---

## How to Run

### 1. Install dependencies
`pip install -r requirements.txt`  
If memo generation uses OpenAI API:  
`pip install openai`
### 2. Add API keys (local only)
Create a file named secrets.env:  
`ALPHAVANTAGE_API_KEY=your_key`  
`OPENAI_API_KEY=your_key`
### 3. Run
`python run_demo.py`

---


## Outputs

| Folder | Contents |
|--------|----------|
| `outputs/` | Three financial statements, ratios(profitability, leverage, growth, efficiency), multiples, DCF forecast, WACC, DCF valuation |
| `outputs/figures/` | Ratio line chart, multiple bar chart and multiple scatter plot |
| `outputs/investment_memo.md` | Generated investment memo |


