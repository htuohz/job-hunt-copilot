#!/usr/bin/env python3
"""
Small helpers for loading local environment configuration.
"""

import os
from pathlib import Path


def load_local_env(base_dir: Path) -> None:
    """Load simple KEY=VALUE pairs from .env if present."""
    env_file = base_dir / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
