"""Path joining for untrusted input."""


def safe_join(base: str, user_path: str) -> str:
    """Join user_path onto base, refusing anything that escapes base."""
    raise NotImplementedError
