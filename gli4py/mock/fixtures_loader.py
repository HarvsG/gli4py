"""Fixtures loader for GL.iNet mock server."""

import copy
import json
import os
from pathlib import Path
from typing import Any

# Default location for test fixtures
PACKAGE_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _resolve_default_fixtures_dir() -> Path:
    if "GLI4PY_FIXTURES_DIR" in os.environ:
        env_dir = Path(os.environ["GLI4PY_FIXTURES_DIR"])
        if env_dir.exists():
            return env_dir
    return PACKAGE_FIXTURES_DIR


DEFAULT_FIXTURES_DIR = _resolve_default_fixtures_dir()


class FixturesLoader:
    """Loads and caches JSON fixtures for the mock router."""

    def __init__(self, fixtures_dir: Path | str | None = None) -> None:
        """Initialize loader with a specific fixtures directory."""
        if fixtures_dir is None:
            self._dir = DEFAULT_FIXTURES_DIR
        else:
            self._dir = Path(fixtures_dir)
        self._cache: dict[str, Any] = {}

    @property
    def fixtures_dir(self) -> Path:
        """Return the fixtures directory."""
        return self._dir

    def load(self, name: str) -> Any:
        """Load a JSON fixture by filename, returning a deep copy to prevent mutation."""
        if not name.endswith(".json"):
            name = f"{name}.json"

        if name not in self._cache:
            file_path = self._dir / name
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Fixture file '{name}' not found in {self._dir}"
                )
            with open(file_path, encoding="utf-8") as f:
                self._cache[name] = json.load(f)

        return copy.deepcopy(self._cache[name])
