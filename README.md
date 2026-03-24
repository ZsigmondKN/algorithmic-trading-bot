# Trading Bot

## Overview
A Python-based trading bot implementing an Exponential Moving Average (EMA) crossover strategy on MetaTrader5. It retrieves market data, computes indicators, and identifies potential buy/sell signals across selected currency pairs.

## Tech Stack
- Python
- MetaTrader5
- pandas

## Key Features
- Connects to MetaTrader5 and retrieves historical price data  
- Calculates EMA indicators and detects crossover signals  
- Supports multiple currency pairs and configurable timeframes  

## How to Run
1. Install MetaTrader5  
2. Install dependencies: `pip install -r requirements.txt`  
3. Add your MT5 credentials in a `.env` file  
4. Run: `python main.py`
---