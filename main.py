from src.trading_bot.bot import TradingBot
from src.trading_bot.config import load_config


def main() -> None:
    config = load_config()
    bot = TradingBot(config)
    bot.run()


if __name__ == "__main__":
    main()
