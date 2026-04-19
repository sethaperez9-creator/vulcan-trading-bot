import os
from dataclasses import dataclass
from dotenv import load_dotenv


def load_config() -> "BotConfig":
    load_dotenv()
    return BotConfig(
        api_key=os.getenv("API_KEY", ""),
        api_secret=os.getenv("API_SECRET", ""),
        symbol=os.getenv("SYMBOL", "BTC/USDT"),
        timeframe=os.getenv("TIMEFRAME", "1h"),
        order_size=float(os.getenv("ORDER_SIZE", "0.001")),
        test_mode=os.getenv("TEST_MODE", "true").lower() == "true",
    )


@dataclass
class BotConfig:
    api_key: str
    api_secret: str
    symbol: str
    timeframe: str
    order_size: float
    test_mode: bool
