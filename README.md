# Trading Bot

A lightweight Python trading bot scaffold for algorithmic trading and exchange integration.

## Setup

1. Install Python 3.11+.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables in `.env`.

## Run

```bash
python main.py
```

## Project Structure

- `main.py` - application entry point.
- `src/trading_bot/` - bot logic, exchange adapter, strategies, and configuration.
- `tests/` - unit tests.
