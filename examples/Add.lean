-- Example: Lean 4 defs with @[export] for Python bindings.
-- Run: lean2py Add.lean -o . --bindings-name add
-- Then in Python: from add import add; add(2, 3)

@[export add] def add (a b : UInt32) : UInt32 := a + b
@[export mul] def mul (a b : UInt32) : UInt32 := a * b
