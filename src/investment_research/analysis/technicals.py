from collections.abc import Sequence


def moving_average(values: Sequence[float], window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be greater than zero")

    averages: list[float | None] = [None] * len(values)
    for index in range(window - 1, len(values)):
        sample = values[index - window + 1 : index + 1]
        averages[index] = sum(sample) / window
    return averages


def daily_returns(values: Sequence[float]) -> list[float]:
    if len(values) < 2:
        return []
    return [(current - previous) / previous for previous, current in zip(values, values[1:])]


def maximum_drawdown(values: Sequence[float]) -> float:
    if not values:
        return 0.0

    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, (value - peak) / peak)
    return drawdown