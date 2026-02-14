-- Example: Array UInt32 -> UInt64 export. Call from Python with a list of ints.
-- Run: uv run lean2py examples/ArraySum.lean -o . --bindings-name array_sum
-- Then: import array_sum; array_sum.sum_arr([1, 2, 3, 4, 5])  # 15

-- foldl : (β → α → β) → β → Array α → β. Use β = UInt64, α = UInt32.
@[export sum_arr] def sumArr (arr : Array UInt32) : UInt64 :=
  Array.foldl (fun (acc : UInt64) (x : UInt32) => acc + x.toUInt64) (0 : UInt64) arr
