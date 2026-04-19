import pytest
from src.trading_bot.strategy import Strategy


def test_generate_signal_buy():
    strategy = Strategy()
    candles = [
        [0, 0, 0, 0, 100],
        [0, 0, 0, 0, 105],
        [0, 0, 0, 0, 110],
    ]
    assert strategy.generate_signal(candles) == "buy"


def test_generate_signal_sell():
    strategy = Strategy()
    candles = [
        [0, 0, 0, 0, 110],
        [0, 0, 0, 0, 105],
        [0, 0, 0, 0, 100],
    ]
    assert strategy.generate_signal(candles) == "sell"


def test_generate_signal_hold():
    strategy = Strategy()
    candles = []
    assert strategy.generate_signal(candles) == "hold"
