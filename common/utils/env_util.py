"""Environment variable loading with layered support (.env, .env.test, .env.prod)"""
import os
from pathlib import Path
import environ


def load_env(base_dir: Path) -> environ.Env:
    env_file = base_dir / ".env"
    if env_file.exists():
        environ.Env.read_env(env_file)

    environment = os.environ.get("RUN_ENV", "").lower()
    env_specific_name = {"dev": ".env.dev", "test": ".env.test", "prod": ".env.prod"}.get(
        environment, ""
    )
    if env_specific_name:
        env_specific = base_dir / env_specific_name
        if env_specific.exists():
            environ.Env.read_env(env_specific, overwrite=True)

    return environ.Env()
