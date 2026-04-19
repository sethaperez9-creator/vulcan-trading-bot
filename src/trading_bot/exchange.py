from typing import Any, Dict
import ccxt


class ExchangeAdapter:
    def __init__(self, api_key: str, api_secret: str, test_mode: bool = True) -> None:
        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        })
        if test_mode:
            self.exchange.set_sandbox_mode(True)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Any:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def create_order(self, symbol: str, side: str, amount: float, price: float = None) -> Dict[str, Any]:
        order_type = "market" if price is None else "limit"
        return self.exchange.create_order(symbol, type=order_type, side=side, amount=amount, price=price)
