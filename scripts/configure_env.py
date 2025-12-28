#!/usr/bin/env python3
"""
Interactive helper to create/update a local .env with OPENAI_API_KEY.

- Prompts securely (hidden input)
- Writes/updates OPENAI_API_KEY in .env
- Sets file permissions to 600

Usage:
  python3 scripts/configure_env.py
  .venv/bin/python scripts/configure_env.py
"""
from __future__ import annotations

import os
import re
import getpass
from pathlib import Path


def main() -> int:
    key = getpass.getpass("Paste OPENAI_API_KEY (input hidden), then press Enter: ").strip()
    if not key:
        print("No key entered. No changes made.")
        return 1

    env_path = Path(".env")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    out: list[str] = []
    found = False
    for line in lines:
        if re.match(r"^\s*OPENAI_API_KEY\s*=", line):
            out.append(f"OPENAI_API_KEY={key}")
            found = True
        else:
            out.append(line)

    if not found:
        out.append(f"OPENAI_API_KEY={key}")

    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)
    print("Wrote OPENAI_API_KEY to .env and set permissions to 600.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
