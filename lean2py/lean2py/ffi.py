"""
Minimal FFI layer for Lean 4: build Array of primitives from Python, call exports, unbox results.

Uses the Lean runtime (libleanshared etc.) to allocate arrays and box/unbox scalars.
Convention: exported Lean functions that take (Array UInt32) or (Array Float) and return
a primitive can be called with a Python list; we build the lean_object* array and call.
"""

import ctypes
import os
import sys
from pathlib import Path

# Lean runtime constants (from lean.h)
LEAN_ARRAY_TAG = 246
LEAN_OBJECT_HEADER_SIZE = 8  # lean_object
LEAN_ARRAY_HEADER_SIZE = LEAN_OBJECT_HEADER_SIZE + 8 + 8  # + m_size + m_capacity


def _lean_box_u32(x: int) -> int:
    """Scalar encoding: on 64-bit Lean uses tagged pointers for small scalars."""
    return ((x & 0xFFFFFFFF) << 1) | 1


def _lean_box_u64(x: int) -> int:
    """UInt64 is stored in a ctor, not a tag. We'd need lean_box_uint64 from runtime."""
    # For now we only support returns that fit in 32-bit or we use the runtime.
    if (x >> 32) == 0:
        return _lean_box_u32(x)
    raise NotImplementedError("64-bit box from Python not implemented; use runtime")


def _get_runtime_lib(lean_bin_dir: str | Path | None):
    """Load the Lean runtime DLL that exports lean_alloc_object, lean_dec_ref_cold."""
    if lean_bin_dir is None:
        return None
    bin_dir = Path(lean_bin_dir)
    if not bin_dir.is_dir():
        return None
    # Lean runtime: alloc/unbox are in libInit_shared on Windows, libleanshared elsewhere
    if sys.platform == "win32":
        names = ["libInit_shared.dll", "libleanshared.dll", "libleanshared_2.dll"]
    elif sys.platform == "darwin":
        names = ["libInit_shared.dylib", "libleanshared.dylib", "libleanshared_2.dylib"]
    else:
        names = ["libInit_shared.so", "libleanshared.so", "libleanshared_2.so"]
    for name in names:
        path = bin_dir / name
        if path.exists():
            try:
                return ctypes.CDLL(str(path))
            except OSError:
                continue
    return None


def _array_u32_to_lean(
    rt: ctypes.CDLL,
    py_list: list[int],
) -> ctypes.c_void_p:
    """Build a Lean Array UInt32 from a Python list. Caller must not free (passed to Lean; it consumes)."""
    n = len(py_list)
    if n == 0:
        # Empty array: capacity 0
        capacity = 0
    else:
        capacity = n
    # lean_alloc_object(size) - size = sizeof(lean_array_object) + capacity * sizeof(void*)
    size = LEAN_ARRAY_HEADER_SIZE + 8 * capacity
    lean_alloc_object = rt.lean_alloc_object
    lean_alloc_object.argtypes = [ctypes.c_size_t]
    lean_alloc_object.restype = ctypes.c_void_p

    ptr = lean_alloc_object(size)
    if not ptr:
        raise RuntimeError("lean_alloc_object failed")
    # Set header: lean_object at 0 (m_rc=1, m_tag=246, m_other=0, m_cs_sz=0)
    # Layout: 4 bytes m_rc=1 (LE), 2 bytes m_cs_sz=0, 1 byte m_other=0, 1 byte m_tag=246
    buf = (ctypes.c_uint8 * size).from_address(ptr)
    buf[0:4] = (1).to_bytes(4, "little")
    buf[4:8] = (LEAN_ARRAY_TAG << 24).to_bytes(4, "little")
    # m_size, m_capacity at offset 8
    buf[8:16] = n.to_bytes(8, "little")
    buf[16:24] = capacity.to_bytes(8, "little")
    # m_data[i] = lean_box_uint32(py_list[i]) = tagged scalar
    for i, x in enumerate(py_list):
        val = _lean_box_u32(x & 0xFFFFFFFF)
        offset = 24 + i * 8
        buf[offset : offset + 8] = val.to_bytes(8, "little")
    return ctypes.c_void_p(ptr)


def _array_f64_to_lean(
    rt: ctypes.CDLL,
    py_list: list[float],
) -> ctypes.c_void_p:
    """Build a Lean Array Float from a Python list. Requires lean_box_float from runtime."""
    # Float is boxed via lean_box_float (ctor), not a tag. We need the runtime.
    # For a minimal implementation we could skip Float arrays or use a different approach.
    raise NotImplementedError("Array Float from Python not yet implemented; use Array UInt32 or String boundary")


def _unbox_u32(rt: ctypes.CDLL, result_ptr: ctypes.c_void_p) -> int:
    """Unbox a Lean UInt32 result (tagged scalar: pointer value is (n<<1)|1)."""
    val = result_ptr.value if result_ptr else 0
    if (val & 1) == 1:
        return (val >> 1) & 0xFFFFFFFF
    raise NotImplementedError("Unboxing boxed UInt32 from Python not implemented")


def _unbox_u64(rt: ctypes.CDLL, result_ptr: ctypes.c_void_p | int) -> int:
    """Unbox a Lean UInt64/Nat result. Tagged scalar or boxed UInt64 ctor (read at ptr+8)."""
    val = getattr(result_ptr, "value", result_ptr) or 0
    if (val & 1) == 1:
        return val >> 1
    # Boxed UInt64: ctor with one uint64 at offset 8 (after lean_object header)
    try:
        addr = int(val) + 8
        raw = (ctypes.c_uint8 * 8).from_address(addr)
        out = int.from_bytes(bytes(raw), "little")
        # Caller owns result; we must decref (lean_dec_ref_cold for non-scalar)
        dec = getattr(rt, "lean_dec_ref_cold", None)
        if dec is not None:
            dec.argtypes = [ctypes.c_void_p]
            dec.restype = None
            dec(ctypes.c_void_p(int(val)))
        return out
    except Exception:
        raise NotImplementedError("Unboxing result from Python not implemented")


def call_array_u32_u64(
    lib: ctypes.CDLL,
    rt: ctypes.CDLL | None,
    symbol: str,
    py_list: list[int],
    lean_bin_dir: str | Path | None,
) -> int:
    """
    Call a Lean export (Array UInt32) -> UInt64 with a Python list.
    Builds the array, calls the symbol, unboxes the result.
    """
    if rt is None:
        rt = _get_runtime_lib(lean_bin_dir)
    if rt is None:
        raise RuntimeError(
            "Lean runtime not found; set LEAN2PY_LEAN_BIN or ensure Lean bin is on PATH"
        )
    arr_ptr = _array_u32_to_lean(rt, py_list)
    func = getattr(lib, symbol, None)
    if func is None:
        raise AttributeError(f"Export not found: {symbol}")
    func.argtypes = [ctypes.c_void_p]
    func.restype = ctypes.c_void_p
    result = func(arr_ptr)
    # Result is standard (caller consumes); we don't dec the array (Lean consumed it)
    return _unbox_u64(rt, result)


def _read_lean_array_u32(rt: ctypes.CDLL, ptr: ctypes.c_void_p) -> list[int]:
    """Read a Lean Array UInt32 at ptr into a Python list. Decrefs the array."""
    if not ptr:
        return []
    addr = ptr.value
    # Header: tag at offset 7 (lean_object m_rc, m_cs_sz, m_other, m_tag)
    tag = (ctypes.c_uint8).from_address(addr + 7).value
    if tag != LEAN_ARRAY_TAG:
        dec = getattr(rt, "lean_dec_ref_cold", None)
        if dec is not None:
            dec.argtypes = [ctypes.c_void_p]
            dec.restype = None
            dec(ptr)
        raise ValueError(f"Expected Lean array (tag 246), got tag {tag}")
    m_size = int.from_bytes((ctypes.c_uint8 * 8).from_address(addr + 8)[:], "little")
    out: list[int] = []
    for i in range(m_size):
        slot_addr = addr + LEAN_ARRAY_HEADER_SIZE + i * 8
        val = int.from_bytes((ctypes.c_uint8 * 8).from_address(slot_addr)[:], "little")
        if (val & 1) == 1:
            out.append((val >> 1) & 0xFFFFFFFF)
        else:
            # Boxed UInt32 - skip for now
            out.append(0)
    dec = getattr(rt, "lean_dec_ref_cold", None)
    if dec is not None:
        dec.argtypes = [ctypes.c_void_p]
        dec.restype = None
        dec(ptr)
    return out


def call_array_u32_array_u32(
    lib: ctypes.CDLL,
    rt: ctypes.CDLL | None,
    symbol: str,
    py_list: list[int],
    lean_bin_dir: str | Path | None,
) -> list[int]:
    """Call (Array UInt32) -> Array UInt32; returns Python list."""
    if rt is None:
        rt = _get_runtime_lib(lean_bin_dir)
    if rt is None:
        raise RuntimeError(
            "Lean runtime not found; set LEAN2PY_LEAN_BIN or ensure Lean bin is on PATH"
        )
    arr_ptr = _array_u32_to_lean(rt, py_list)
    func = getattr(lib, symbol, None)
    if func is None:
        raise AttributeError(f"Export not found: {symbol}")
    func.argtypes = [ctypes.c_void_p]
    func.restype = ctypes.c_void_p
    result = func(arr_ptr)
    return _read_lean_array_u32(rt, result)


def call_array_u32_flexible(
    lib: ctypes.CDLL,
    rt: ctypes.CDLL | None,
    symbol: str,
    py_list: list[int],
    lean_bin_dir: str | Path | None,
) -> int | list[int]:
    """
    Call a Lean export (Array UInt32) -> _ with a Python list.
    If the result is an array, returns list[int]; otherwise unboxes to int.
    """
    if rt is None:
        rt = _get_runtime_lib(lean_bin_dir)
    if rt is None:
        raise RuntimeError(
            "Lean runtime not found; set LEAN2PY_LEAN_BIN or ensure Lean bin is on PATH"
        )
    arr_ptr = _array_u32_to_lean(rt, py_list)
    func = getattr(lib, symbol, None)
    if func is None:
        raise AttributeError(f"Export not found: {symbol}")
    func.argtypes = [ctypes.c_void_p]
    func.restype = ctypes.c_void_p
    result = func(arr_ptr)
    val = getattr(result, "value", result) or 0
    # Tagged scalar (low bit 1) -> return int
    if val & 1:
        return _unbox_u64(rt, result)
    # Pointer -> assume array
    try:
        return _read_lean_array_u32(rt, ctypes.c_void_p(val) if not isinstance(result, ctypes.c_void_p) else result)
    except ValueError:
        return _unbox_u64(rt, result)


def call_array_u32_u32(
    lib: ctypes.CDLL,
    rt: ctypes.CDLL | None,
    symbol: str,
    py_list: list[int],
    lean_bin_dir: str | Path | None,
) -> int:
    """Call (Array UInt32) -> UInt32."""
    if rt is None:
        rt = _get_runtime_lib(lean_bin_dir)
    if rt is None:
        raise RuntimeError("Lean runtime not found")
    arr_ptr = _array_u32_to_lean(rt, py_list)
    func = getattr(lib, symbol, None)
    if func is None:
        raise AttributeError(f"Export not found: {symbol}")
    func.argtypes = [ctypes.c_void_p]
    func.restype = ctypes.c_void_p
    result = func(arr_ptr)
    return _unbox_u32(rt, result)
