"""CLI: lean2py <file.lean> [--out-dir DIR] → builds and writes Python bindings."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .build import run_cmd
from .errors import RunResult
from .pipeline import run_detailed

EXIT_GENERIC = 1
EXIT_INVALID = 2
EXIT_LAKE = 3
EXIT_NO_EXPORTS = 4


def _failure_exit_code(res: RunResult) -> int:
    if res.ok:
        return 0
    if res.lake_build is not None and not res.lake_build.ok:
        return EXIT_LAKE
    joined = "\n".join(res.errors)
    if "@[export" in joined:
        return EXIT_NO_EXPORTS
    return EXIT_INVALID


def cmd_doctor() -> int:
    """Print whether ``lean`` / ``lake`` are usable (PATH + quick version check)."""
    elan_bin = Path.home() / ".elan" / "bin"
    print(f"Expected elan bin: {elan_bin} ({'exists' if elan_bin.is_dir() else 'missing'})")
    lean = shutil.which("lean")
    lake = shutil.which("lake")
    print(f"lean on PATH: {lean or '(not found)'}")
    print(f"lake on PATH: {lake or '(not found)'}")
    ok = True
    if lean:
        r = run_cmd(["lean", "--version"], cwd=None, timeout=60.0)
        print(r.stdout.strip() or "(no stdout)")
        if not r.ok:
            ok = False
            print(r.stderr, file=sys.stderr)
    else:
        ok = False
    if lake:
        r = run_cmd(["lake", "--version"], cwd=None, timeout=60.0)
        print(r.stdout.strip() or "(no stdout)")
        if not r.ok:
            ok = False
            print(r.stderr, file=sys.stderr)
    else:
        ok = False
    if not ok:
        print(
            "\nInstall: https://github.com/leanprover/elan — then open a new terminal "
            "or use .vscode/settings.json here (Windows: prepends %USERPROFILE%\\.elan\\bin).",
            file=sys.stderr,
        )
        return EXIT_GENERIC
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        return cmd_doctor()

    parser = argparse.ArgumentParser(
        description="Lean 4 → build → Python bindings. No AI. Put @[export name] on defs.",
        epilog="Check toolchain: lean2py doctor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "lean",
        type=Path,
        help="Path to .lean file or Lean project directory",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
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
        "--lib-name",
        default="LeanExport",
        help="Lake lean_lib / shared library name (default: LeanExport)",
    )
    parser.add_argument(
        "--mathlib",
        action="store_true",
        help="Single-file only: add Mathlib to the build (first run fetches and builds Mathlib)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print lake command output on failure",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print errors (no success paths)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Raise Lean2PyError on failure (for debugging); implies non-zero exit if uncaught",
    )
    args = parser.parse_args()

    if not args.lean.exists():
        print(f"Error: {args.lean} not found", file=sys.stderr)
        return EXIT_INVALID

    if args.verbose and args.quiet:
        print("Error: use either --verbose or --quiet, not both", file=sys.stderr)
        return EXIT_GENERIC

    if args.strict and args.quiet:
        print("Error: --strict is not compatible with --quiet", file=sys.stderr)
        return EXIT_GENERIC

    res = run_detailed(
        args.lean,
        output_dir=args.out_dir,
        lib_name=args.lib_name,
        bindings_name=args.bindings_name.replace(".py", ""),
        use_mathlib=args.mathlib,
    )

    if args.strict:
        res.raise_for_status()

    if not res.ok:
        for line in res.errors:
            print(line, file=sys.stderr)
        if args.verbose and res.lake_build is not None:
            cmd = " ".join(res.lake_build.args)
            print(f"\n[lean2py] command: {cmd}", file=sys.stderr)
            if res.lake_build.stdout.strip():
                print("\n--- stdout ---\n", res.lake_build.stdout, file=sys.stderr, sep="")
            if res.lake_build.stderr.strip():
                print("\n--- stderr ---\n", res.lake_build.stderr, file=sys.stderr, sep="")
        return _failure_exit_code(res)

    if not args.quiet:
        print(f"Wrote: {res.py_path}")
        if res.lib_path is None:
            print(
                "Note: shared library not produced by lake. Build it and set LEAN2PY_LIB.",
                file=sys.stderr,
            )
        else:
            print(f"Lib:   {res.lib_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
