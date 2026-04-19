from typing import List


class Strategy:
    def generate_signal(self, candles: List[List[float]]) -> str:
        if not candles:
            return "hold"

        closes = [candle[4] for candle in candles]
        if len(closes) < 3:
            return "hold"

        if closes[-1] > closes[-2] > closes[-3]:
            return "buy"
        if closes[-1] < closes[-2] < closes[-3]:
            return "sell"
        return "hold"
