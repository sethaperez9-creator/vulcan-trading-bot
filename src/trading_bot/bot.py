from typing import List
from .config import BotConfig
from .exchange import ExchangeAdapter
from .strategy import Strategy


class TradingBot:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.exchange = ExchangeAdapter(config.api_key, config.api_secret, config.test_mode)
        self.strategy = Strategy()

    def run(self) -> None:
        print(f"Starting trading bot for {self.config.symbol} in {'test' if self.config.test_mode else 'live'} mode")
        candles = self._load_market_data()
        signal = self.strategy.generate_signal(candles)
        self._execute_signal(signal)

    def _load_market_data(self) -> List[List[float]]:
        print("Fetching recent candles...")
        return self.exchange.fetch_ohlcv(self.config.symbol, self.config.timeframe, limit=20)

    def _execute_signal(self, signal: str) -> None:
        print(f"Signal: {signal}")
        if signal == "buy":
            order = self.exchange.create_order(self.config.symbol, "buy", self.config.order_size)
            print("Order placed:", order)
        elif signal == "sell":
            order = self.exchange.create_order(self.config.symbol, "sell", self.config.order_size)
            print("Order placed:", order)
        else:
            print("No trade executed.")
