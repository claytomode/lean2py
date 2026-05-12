"""Tests for generated binding source (no Lean toolchain required)."""

from pathlib import Path

from lean2py.lean2py.bindings import generate_python_bindings
from lean2py.lean2py.parser import Export


def test_generated_bindings_thread_lock_and_no_silent_except(tmp_path: Path) -> None:
    exports = [Export(c_symbol="f", lean_name="f")]
    out = tmp_path / "gen.py"
    text = generate_python_bindings(exports, "/tmp/libLeanExport.so", out)
    assert "_lib_lock = threading.Lock()" in text
    assert "with _lib_lock:" in text
    assert "except (AttributeError" not in text
    assert "call_array_u32_flexible" in text
    content = out.read_text(encoding="utf-8")
    assert content == text
