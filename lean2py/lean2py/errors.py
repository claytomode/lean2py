"""Typed errors and structured results for lean2py."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class Lean2PyError(Exception):
    """Base exception for lean2py."""

    pass


class InvalidInputError(Lean2PyError):
    """Input path or options are invalid."""

    pass


class NoExportsError(Lean2PyError):
    """No `@[export ...]` definitions were found."""

    pass


class LakeBuildError(Lean2PyError):
    """``lake`` or Lean build step failed."""

    def __init__(
        self,
        message: str,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = -1,
        command: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.command = command


@dataclass(frozen=True)
class CmdResult:
    """Outcome of a subprocess (e.g. ``lake build``)."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _trim(s: str, max_chars: int = 48_000) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars // 2] + "\n... [truncated] ...\n" + s[-max_chars // 2 :]


@dataclass
class RunResult:
    """Structured result from :func:`run_detailed`."""

    ok: bool
    lib_path: Path | None
    py_path: Path | None
    errors: list[str] = field(default_factory=list)
    lake_build: CmdResult | None = None

    def raise_for_status(self) -> None:
        """Raise the most specific :class:`Lean2PyError` if ``ok`` is false."""
        if self.ok:
            return
        if self.lake_build and not self.lake_build.ok:
            msg = self.errors[0] if self.errors else "Lake build failed"
            raise LakeBuildError(
                msg,
                stdout=_trim(self.lake_build.stdout),
                stderr=_trim(self.lake_build.stderr),
                returncode=self.lake_build.returncode,
                command=self.lake_build.args,
            )
        joined = "\n".join(self.errors) if self.errors else ""
        if "@[export" in joined or "No @[export" in joined:
            raise NoExportsError(joined or "No exports found")
        if joined and (
            "Expected a .lean" in joined
            or "Not a directory" in joined
            or "No lakefile" in joined
            or "No .lean source" in joined
        ):
            raise InvalidInputError(joined)
        raise Lean2PyError(joined or "lean2py run failed")
