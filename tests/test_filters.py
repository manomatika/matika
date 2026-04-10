import pytest
from matika.main import format_num

def test_format_num_en():
    assert format_num(1234.56, "en") == "1,234.56"
    assert format_num("1234.56", "en") == "1,234.56"

def test_format_num_es():
    assert format_num(1234.56, "es") == "1.234,56"
    assert format_num("1234.56", "es") == "1.234,56"

def test_format_num_invalid():
    assert format_num("abc", "en") == "abc"
    assert format_num(None, "en") is None
