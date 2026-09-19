"""Arithmetic helpers."""


def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("cannot divide by zero")
    return a / b
