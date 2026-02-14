-- Mergesort: (Array UInt32) -> Array UInt32. Call from Python with a list of ints.
-- Run: lean2py examples/MergeSort.lean -o . --bindings-name merge_sort
-- Then: import merge_sort; merge_sort.mergesort([3, 1, 4, 1, 5, 9, 2, 6])  # [1, 1, 2, 3, 4, 5, 6, 9]

def merge (a b : List UInt32) : List UInt32 :=
  match a, b with
  | [], bs => bs
  | as_, [] => as_
  | x :: xs, y :: ys =>
    if x ≤ y then x :: merge xs (y :: ys) else y :: merge (x :: xs) ys

def split (l : List UInt32) : List UInt32 × List UInt32 :=
  let n := l.length / 2
  (l.take n, l.drop n)

partial def sort (l : List UInt32) : List UInt32 :=
  match l with
  | [] => []
  | [x] => [x]
  | _ =>
    let (left, right) := split l
    merge (sort left) (sort right)

@[export mergesort] def mergesort (arr : Array UInt32) : Array UInt32 :=
  (sort arr.toList).toArray
