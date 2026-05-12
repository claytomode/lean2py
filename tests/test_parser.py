"""Tests for Lean export parsing (no Lean toolchain required)."""

from lean2py.lean2py.parser import Export, parse_exports


def test_parse_quoted_export() -> None:
    src = """
@[export "my_add"]
def myAdd (a b : UInt32) : UInt32 := a + b
"""
    out = parse_exports(src)
    assert out == [Export(c_symbol="my_add", lean_name="myAdd")]


def test_parse_unquoted_export() -> None:
    src = """
@[export my_mul]
def myMul (a b : UInt32) : UInt32 := a * b
"""
    out = parse_exports(src)
    assert out == [Export(c_symbol="my_mul", lean_name="myMul")]


def test_parse_optional_following_attr_block() -> None:
    src = """
@[export sum_arr] [never_extract]
def sumArr (xs : Array UInt32) : UInt64 := 0
"""
    out = parse_exports(src)
    assert len(out) == 1
    assert out[0].c_symbol == "sum_arr"
    assert out[0].lean_name == "sumArr"


def test_parse_empty() -> None:
    assert parse_exports("def n := 1") == []
