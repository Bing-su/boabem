import pytest
import boabem


def test_sum_as_string():
    assert boabem.sum_as_string(1, 1) == "2"
