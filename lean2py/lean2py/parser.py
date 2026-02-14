"""Parse Lean 4 source for @[export "c_name"] / @[export c_name] to get C symbol names."""

import re
from dataclasses import dataclass


@dataclass
class Export:
    """One exported symbol from Lean."""
    c_symbol: str
    lean_name: str


def parse_exports(lean_source: str) -> list[Export]:
    """
    Find all @[export ...] def <name> in Lean source.
    Returns list of (C symbol, Lean def name). C symbol is from the attribute.
    """
    out: list[Export] = []
    # @[export "my_add"] or @[export my_add] before a def
    # Pattern: @[export "symbol"] or @[export symbol], then later def leanName
    pattern = re.compile(
        r"@\s*\[\s*export\s+"
        r"(?:\"([^\"]+)\"|(\w+))"  # "quoted" or unquoted name
        r"\s*\]\s*"
        r"(?:\s*\[[^\]]*\])*"       # optional other attributes
        r"\s*def\s+(\w+)",          # def name
        re.MULTILINE | re.DOTALL,
    )
    for m in pattern.finditer(lean_source):
        c_symbol = m.group(1) or m.group(2) or ""
        lean_name = m.group(3) or ""
        if c_symbol and lean_name:
            out.append(Export(c_symbol=c_symbol, lean_name=lean_name))
    return out
