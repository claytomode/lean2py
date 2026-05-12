"""Tests for RunResult.raise_for_status."""

import pytest
from lean2py.lean2py.errors import (
    CmdResult,
    InvalidInputError,
    LakeBuildError,
    NoExportsError,
    RunResult,
)


def test_raise_lake_build() -> None:
    r = RunResult(
        False,
        None,
        None,
        errors=["Lake build failed (see lake_build stdout/stderr)."],
        lake_build=CmdResult(("lake", "build"), 1, "", "error: boom"),
    )
    with pytest.raises(LakeBuildError) as ei:
        r.raise_for_status()
    assert ei.value.returncode == 1
    assert "boom" in ei.value.stderr


def test_raise_no_exports() -> None:
    r = RunResult(
        False,
        None,
        None,
        errors=["No @[export ...] definitions found in x.lean."],
    )
    with pytest.raises(NoExportsError):
        r.raise_for_status()


def test_raise_invalid_input() -> None:
    r = RunResult(
        False,
        None,
        None,
        errors=["No lakefile.lean or lakefile.toml in /tmp/foo."],
    )
    with pytest.raises(InvalidInputError):
        r.raise_for_status()
