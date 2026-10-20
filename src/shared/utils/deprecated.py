import warnings
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

F = TypeVar("F", bound=Callable)

DEPRECATED_LABEL = "`Desuso`"


def deprecated(reason: str | None = None) -> Callable[[F], F]:
    """Marca una función como en desuso: emite DeprecationWarning al llamarla
    y permite al menú mostrar la etiqueta DEPRECATED_LABEL."""

    def decorator(func: F) -> F:
        message = f"{func.__name__} está en desuso"
        if reason:
            message += f": {reason}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        wrapper.__deprecated__ = reason or True
        return wrapper

    return decorator


def is_deprecated(func: object) -> bool:
    return bool(getattr(func, "__deprecated__", False))


def deprecation_reason(func: object) -> str | None:
    marker = getattr(func, "__deprecated__", None)
    return marker if isinstance(marker, str) else None
