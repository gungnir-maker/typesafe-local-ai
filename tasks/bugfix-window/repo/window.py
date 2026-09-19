"""Sequence windows."""


def last_n(items, n):
    """Return the last n items of items, in order."""
    if n < 0:
        raise ValueError("n must not be negative")
    start = len(items) - n
    return list(items[start:len(items) - 1])
