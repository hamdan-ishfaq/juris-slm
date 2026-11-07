#!/usr/bin/env python3
"""Convert scripts/*.sh to Unix LF line endings (fixes WSL set: pipefail errors)."""
from pathlib import Path

for path in sorted(Path(__file__).parent.glob("*.sh")):
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    path.write_bytes(data)
    print(f"fixed: {path.name}")
