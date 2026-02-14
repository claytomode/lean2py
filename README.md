# lean2py

**Lean 4 → compiled C → Python bindings.** Write Lean 4, build with Lake, get a Python module you can import and call.

## Install

From the repo (development):

```bash
git clone https://github.com/claytomode/lean2py.git
cd lean2py
uv sync
```

The `lean2py` CLI is available after `uv sync` (or use `uv run lean2py`).

## Quick start

1. Write Lean 4 code and mark exports with `@[export c_name]` (identifier, not string):

   ```lean
   @[export my_add] def myAdd (a b : UInt32) : UInt32 := a + b
   ```

2. Run the pipeline (builds with `lake`, generates Python bindings):

   ```bash
   lean2py path/to/MyLib.lean -o .
   ```

   Or: `uv run lean2py path/to/MyLib.lean -o .`

3. Use the generated module:

   ```python
   import lean_export
   lean_export.myAdd(1, 2)  # calls the Lean-compiled function
   ```

   Set `LEAN2PY_LIB` to the path of the shared library (`.so` / `.dll` / `.dylib`) if it’s not in the default location.

## Requirements

- **Lean 4** (and `lake` on your PATH), e.g. via [elan](https://github.com/leanprover/elan).
- Python 3.12+.

## Single file vs project

- **Single `.lean` file:** We create a minimal Lake project in `.lean2py_build/`, run `lake build`, then build the shared library next to the generated `.py`. Use `@[export symbol] def ...` for each function you want from Python. Add `--mathlib` to build with Mathlib (first run is slow).
- **Directory:** Pass a Lean project directory (with `lakefile.lean`); we run `lake build` there and generate bindings from all `@[export ...]` defs in the tree.

## Shared library

We run `lake build` and the shared facet so Lake produces a `.so`/`.dll`/`.dylib`. If that fails, we still write the bindings; set `LEAN2PY_LIB` to your built lib path.

## Mathlib and other dependencies

- **Single file:** Use `--mathlib` so the generated lakefile adds `require mathlib from git "..."`. The first build will fetch and compile Mathlib (slow); later builds are incremental.
- **Existing project:** Point lean2py at the **directory** that contains your `lakefile.lean` (with Mathlib or any deps you already use). We run `lake build` there and collect all `@[export ...]` defs.

## Complex types (List, Option, custom types)

Exported functions that use only **primitive** types (`UInt32`, `Float`, etc.) get clean C signatures and work with the generated bindings. For **complex** types (e.g. `List α`, `Option β`), Lean compiles them to `lean_object*`; calling from Python would require marshalling between Python objects and Lean’s heap. Two practical options:

1. **Serialization boundary:** Export functions that take/return `String` or `ByteArray`. In Lean, decode (e.g. JSON) into your types, compute, then encode back. Python sends/receives strings; no lean_object* on the boundary.
2. **Future:** A proper FFI layer could wrap Lean’s runtime and expose helpers to build/decode `lean_object*` (lists, options, etc.); that’s not implemented yet.

## Project layout

- `lean2py/lean2py/` — Parser (`@[export]`), Lake build, ctypes bindings generator, CLI.
- `examples/` — Sample Lean files with `@[export]` defs.

## License

See repository.
