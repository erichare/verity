# verity-x3p (Python)

Python binding to the [Verity](https://github.com/erichare/verity) native X3P
(ISO 25178-72) reader/writer. Backed by the `verity-x3p` Rust core, so files
round-trip bit-identically with every other Verity language binding.

```python
import verity_x3p

s = verity_x3p.read_x3p("scan.x3p")          # verifies the stored MD5
print(s.nx, s.ny, s.data.shape, s.data.dtype)  # 741 419 (419, 741) float64

# s.data and s.mask are NumPy arrays of shape (ny, nx).
verity_x3p.write_x3p(s, "copy.x3p", z_type="D")
```

## Build from source

```bash
maturin develop            # build + install into the active venv
# or
maturin build --release    # produce a wheel under target/wheels/
```

Requires a Rust toolchain and NumPy. Built as an `abi3` wheel (CPython 3.9+).
