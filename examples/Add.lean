-- Example: Lean 4 defs with @[export] for Python bindings.
-- Run: uv run python -m bigo_gen.lean2py.cli Add.lean -o . --bindings-name add
-- Then in Python: from add import add; add(2, 3)

@[export add] def add (a b : UInt32) : UInt32 := a + b
@[export mul] def mul (a b : UInt32) : UInt32 := a * b
