"""Prefixed formatters."""


def make_formatters(prefixes):
    """Return one formatter function per prefix."""
    formatters = []
    for prefix in prefixes:
        def format_value(value):
            return prefix + ": " + value
        formatters.append(format_value)
    return formatters
