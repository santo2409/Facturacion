"""Tests del decorador @deprecated (spec 019, AC-01..AC-03)."""

import warnings

import pytest

from src.shared.utils.deprecated import (
    DEPRECATED_LABEL,
    deprecated,
    deprecation_reason,
    is_deprecated,
)


def test_decorated_function_keeps_result_name_and_doc():
    @deprecated()
    def add(a, b=1):
        """Suma."""
        return a + b

    with pytest.warns(DeprecationWarning):
        result = add(2, b=3)

    assert result == 5
    assert add.__name__ == "add"
    assert add.__doc__ == "Suma."


def test_call_emits_deprecation_warning_with_reason():
    @deprecated("usar X")
    def old():
        return "ok"

    with pytest.warns(DeprecationWarning, match="usar X"):
        assert old() == "ok"


def test_call_without_reason_warns_with_function_name():
    @deprecated()
    def old():
        return None

    with pytest.warns(DeprecationWarning, match="old"):
        old()


def test_is_deprecated_and_reason():
    @deprecated("usar X")
    def with_reason():
        pass

    @deprecated()
    def without_reason():
        pass

    def plain():
        pass

    assert is_deprecated(with_reason) is True
    assert is_deprecated(without_reason) is True
    assert is_deprecated(plain) is False
    assert deprecation_reason(with_reason) == "usar X"
    assert deprecation_reason(without_reason) is None
    assert deprecation_reason(plain) is None


def test_non_deprecated_function_does_not_warn():
    def plain():
        return 1

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert plain() == 1


def test_label_constant():
    assert DEPRECATED_LABEL == "`Desuso`"
