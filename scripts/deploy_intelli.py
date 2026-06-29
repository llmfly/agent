#!/usr/bin/env python3
"""Unified deployment entrypoint for Intelli Engine environments."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_env_config(env_name: str) -> Path:
    candidates = (
        REPO_ROOT / "deploy" / "envs" / f"{env_name}.conf",
        REPO_ROOT / "deploy" / "envs" / f"{env_name}.baremetal.conf",
        REPO_ROOT / f".deploy-{env_name}.conf",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = "\n  ".join(str(path) for path in candidates)
    raise SystemExit(f"Deployment env not found: {env_name}\nSearched:\n  {searched}")


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Intelli Engine to a named environment.")
    parser.add_argument("--env", required=True, help="Environment name, e.g. dev, 018-070, prod.")
    parser.add_argument("--mode", choices=("baremetal", "docker"), required=True, help="Deployment mode.")
    parser.add_argument("--dry-run", action="store_true", help="Show target and validate config without deploying.")
    parser.add_argument("--skip-runtime-install", action="store_true", help="Bare-metal only: skip Python/Node/uv installation checks.")
    args = parser.parse_args()

    if args.mode == "baremetal":
        config_path = resolve_env_config(args.env)
        cmd = [sys.executable, "scripts/deploy_baremetal.py", "--config", str(config_path.relative_to(REPO_ROOT))]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.skip_runtime_install:
            cmd.append("--skip-runtime-install")
        return run(cmd)

    if args.dry_run:
        print("Docker deployment uses local repo config.yaml/.env and scripts/deploy.sh.")
        print("Command: bash scripts/deploy.sh")
        return 0
    return run(["bash", "scripts/deploy.sh"])


if __name__ == "__main__":
    raise SystemExit(main())
