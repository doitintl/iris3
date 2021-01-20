import pytest

from plugin import Plugin


testdata = [
    ("a.b", "a_b"),
    ("a b", "a_b"),
    (" a b", "_a_b"),
    ("ר", "ר"),
]


@pytest.mark.parametrize("s,expected", testdata)
def test_legal(s, expected):
    out = Plugin._make_legal_label_value(s)
    assert out == expected
