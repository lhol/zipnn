# ZipNN-compat – Build, Run & Release Guide

This document covers everything needed to get from a fresh machine to a
published PyPI package named **zipnn-compat** – a Windows-compatible fork of
ZipNN that fixes the C-extension crashes described in `architecture.md`.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Set Up the Environment](#2-clone--set-up-the-environment)
3. [Build the C Extension](#3-build-the-c-extension)
4. [Run & Verify](#4-run--verify)
5. [Build a Release Package (wheel + sdist)](#5-build-a-release-package-wheel--sdist)
6. [Publish to PyPI as ZNNcompat](#6-publish-to-pypi-as-znncompat)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### All platforms

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.9 | 3.11 or 3.13 recommended; must be 64-bit |
| Git | any recent | needed for `git submodule` |
| numpy | 1.17.0 | installed automatically via pip |
| safetensors | 0.4.0 | installed automatically via pip |
| torch | 2.0.0 | optional; only needed for `input_format='torch'` |

### Windows (additional)

| Requirement | Version | Where to get it |
|---|---|---|
| **Visual Studio 2019 or 2022** | Community edition is fine | https://visualstudio.microsoft.com/ |
| **"Desktop development with C++" workload** | included in VS installer | required – provides `cl.exe`, Windows SDK, UCRT |
| **Windows SDK** | 10.0.19041 or later | installed as part of the VS C++ workload |

> **Important:** `setup.py` invokes MSVC (`cl.exe`) via `setuptools`. You do
> **not** need to run a "Developer Command Prompt" manually – `setuptools`
> locates the compiler automatically through the VS installation registry.
> If the build fails with *"unable to find vcvarsall.bat"*, open the Visual
> Studio Installer and add the **C++ build tools** workload.

### Linux

| Requirement | Package name (apt / dnf) |
|---|---|
| GCC ≥ 9 | `build-essential` (Debian/Ubuntu) · `gcc` (Fedora/RHEL) |
| Python headers | `python3-dev` (Debian/Ubuntu) · `python3-devel` (Fedora/RHEL) |

```bash
# Debian / Ubuntu
sudo apt install build-essential python3-dev python3-venv git

# Fedora / RHEL
sudo dnf install gcc gcc-c++ python3-devel git
```

### macOS

| Requirement | How to install |
|---|---|
| Xcode Command Line Tools | `xcode-select --install` |
| Python 3.9+ | https://www.python.org or `brew install python` |

```bash
xcode-select --install
```

---

## 2. Clone & Set Up the Environment

### Step 1 – Clone the repository with submodules

```bash
git clone --recurse-submodules https://github.com/lhol/zipnn.git
cd zipnn
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

This populates `include/FiniteStateEntropy/` (Huffman/FSE encoder) and
`include/zstd/` (Zstandard reference, not compiled).

### Step 2 – Create a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3 – Install Python dependencies

```bash
pip install --upgrade pip
pip install numpy safetensors packaging
# Optional – only needed for torch tensor support:
pip install torch
# Optional – only needed for ZSTD / LZ4 / Snappy compression methods:
pip install zstandard lz4 python-snappy
```

---

## 3. Build the C Extension

The core compression engine (`zipnn_core`) is a compiled C extension. It must
be built before the Python package can be used.

```bash
python setup.py build_ext --inplace
```

A successful build produces a `.pyd` file on Windows or a `.so` file on
Linux/macOS in the project root:

```
zipnn_core.cp313-win_amd64.pyd    ← Windows, Python 3.13
zipnn_core.cpython-313-x86_64-linux-gnu.so  ← Linux, Python 3.13
```

The exact filename encodes the Python version and platform; `import
zipnn_core` finds the right file automatically.

### What `setup.py` does

1. Runs `git submodule update --init --recursive` (safe to re-run).
2. Compiles `csrc/zipnn_core.c`, `csrc/data_manipulation_dtype16.c`,
   `csrc/data_manipulation_dtype32.c`, and the six FiniteStateEntropy C files.
3. Links everything into a single shared library.

> **Windows note:** The Python `.lib` import library is located automatically
> via `sys.prefix`. No hardcoded paths are used.

---

## 4. Run & Verify

### Quick smoke test (bytes)

```bash
python simple_example.py
```

Expected output (numbers will vary):
```
Generate a 1MB byte string …
Compressing byte data of size 1048576 bytes, using 16 threads.
Compressed … Remaining size is 0.02% of original.
Decompressing …
Are the original and decompressed byte strings the same? [BYTES] True
```

### Torch tensor test (requires torch)

```bash
python simple_example_torch.py
```

### Inline test (no extra files)

```python
from zipnn import ZipNN

zpn = ZipNN(method='huffman', bytearray_dtype='bfloat16')
data = bytearray(b'\xAB\xCD' * (128 * 1024))   # 256 KB, use bytearray not bytes
snapshot = bytes(data)                           # keep a copy before compress modifies it

compressed   = zpn.compress(data)
decompressed = zpn.decompress(compressed)

assert bytes(decompressed) == snapshot, "Round-trip failed!"
print(f"OK – compressed to {len(compressed)/len(snapshot)*100:.1f}% of original")
```

> **Note:** Always pass a `bytearray` (mutable) as input, not a `bytes`
> object. The C extension rewrites the buffer in-place during bit-reordering
> and reverts it after splitting; a `bytes` object will appear to change if
> you hold a reference to it across the compress call.

### Compress / decompress a file

```bash
python scripts/zipnn_compress_file.py path/to/model.bin
python scripts/zipnn_decompress_file.py path/to/model.bin.znn
```

### Run the test suite

```bash
python tests/simple_stress_tests.py
```

---

## 5. Build a Release Package (wheel + sdist)

### Step 1 – Install build tools

```bash
pip install build wheel twine
```

### Step 2 – Rename the package to ZNNcompat

Edit `setup.py` and change the `name` field:

```python
setup(
    name="ZNNcompat",          # ← changed from "zipnn"
    version="0.5.4",
    ...
)
```

Also update the `description` to make the fork's purpose clear:

```python
description="ZipNN – Windows-compatible build (ZNNcompat fork)",
```

### Step 3 – Build the source distribution and wheel

```bash
python -m build
```

This creates two files in `dist/`:

```
dist/
  ZNNcompat-0.5.4.tar.gz          ← source distribution (sdist)
  ZNNcompat-0.5.4-cp313-cp313-win_amd64.whl   ← binary wheel (Windows)
```

> The wheel filename encodes the Python version (`cp313`), ABI, and platform.
> Users on a different platform or Python version will fall back to the sdist
> and compile from source, so the sdist **must** include the `csrc/` and
> `include/` directories. This is handled by `MANIFEST.in`.

### Building wheels for multiple Python versions

If you want to distribute pre-built wheels for Python 3.9 – 3.13, repeat the
build with each interpreter or use **cibuildwheel**:

```bash
pip install cibuildwheel
cibuildwheel --platform windows
```

`cibuildwheel` creates all wheels in `wheelhouse/`. Push them all to PyPI.

---

## 6. Publish to PyPI as ZNNcompat

### Step 1 – Create a PyPI account

Go to https://pypi.org/account/register/ and verify your email address.

### Step 2 – Generate an API token

1. Log in at https://pypi.org.
2. Go to **Account settings → API tokens → Add API token**.
3. Scope: *Entire account* for the first upload; narrow to the project
   afterwards.
4. Copy the token – it starts with `pypi-`.

### Step 3 – Store the token

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers = pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

Or export as environment variable (CI-friendly):

```bash
# Linux / macOS
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE

# Windows PowerShell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-YOUR_TOKEN_HERE"
```

### Step 4 – Test on TestPyPI first (recommended)

```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ ZNNcompat
```

Check at https://test.pypi.org/project/ZNNcompat/ that the page renders
correctly (README, classifiers, version).

### Step 5 – Upload to the real PyPI

```bash
twine upload dist/*
```

Verify at https://pypi.org/project/ZNNcompat/.

### Step 6 – Install from PyPI (end-user command)

```bash
pip install ZNNcompat
```

Users with a matching pre-built wheel get it immediately; others compile from
the sdist (requires a C compiler and the same prerequisites as above).

### Updating a release

Increment `version` in `setup.py` (PyPI does not allow re-uploading the same
version), rebuild with `python -m build`, then run `twine upload dist/*` again.

---

## 7. Troubleshooting

### `error: Microsoft Visual C++ 14.0 or greater is required`

Install the **Desktop development with C++** workload via the Visual Studio
Installer. Do **not** install only Build Tools without the SDK.

### `ModuleNotFoundError: No module named 'zipnn_core'`

The extension was not built, or was built for a different Python version.
Run `python setup.py build_ext --inplace` again with the same interpreter
you use to run the code.

### `Windows fatal exception: access violation` on import

This was the original bug (see `architecture.md` §7). Make sure you are using
the fixed source from this repository, not the upstream `zipnn/zipnn` repo.

### `git submodule update` fails in a CI environment

Add `--depth 1` to the clone:
```bash
git clone --recurse-submodules --depth 1 https://github.com/lhol/zipnn.git
```

### `twine upload` returns `400 File already exists`

PyPI does not allow re-uploading the same version. Bump the version number in
`setup.py`, rebuild, and upload again.

### Build succeeds but `import zipnn_core` raises `ImportError: DLL load failed`

On Windows, the runtime DLLs (`VCRUNTIME140.dll`, `python3XX.dll`) must be on
the `PATH` or in the same directory as the `.pyd` file. Installing the
[Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
resolves most cases.
