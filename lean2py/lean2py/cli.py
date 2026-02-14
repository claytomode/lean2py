"""CLI: lean2py <file.lean> [--out-dir DIR] → builds and writes Python bindings."""

import argparse
import sys
from pathlib import Path

from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lean 4 → build → Python bindings. No AI. Put @[export name] on defs."
    )
    parser.add_argument(
        "lean",
        type=Path,
        help="Path to .lean file or Lean project directory",
    )
    parser.add_argument(
        "--out-dir", "-o",
        type=Path,
        default=None,
        help="Directory for generated .py (default: same as input)",
    )
    parser.add_argument(
        "--bindings-name",
        default="lean_export",
        help="Name of generated Python module file (default: lean_export.py)",
    )
    parser.add_argument(
        "--mathlib",
        action="store_true",
        help="Single-file only: add Mathlib to the build (first run fetches and builds Mathlib)",
    )
    args = parser.parse_args()
    if not args.lean.exists():
        print(f"Error: {args.lean} not found", file=sys.stderr)
        return 1
    lib_path, py_path = run(
        args.lean,
        output_dir=args.out_dir,
        bindings_name=args.bindings_name.replace(".py", ""),
        use_mathlib=args.mathlib,
    )
    if py_path is None:
        print("Error: no @[export ...] defs found or lake build failed", file=sys.stderr)
        return 1
    print(f"Wrote: {py_path}")
    if lib_path is None:
        print("Note: shared library not produced by lake. Build it and set LEAN2PY_LIB.", file=sys.stderr)
    else:
        print(f"Lib:   {lib_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
