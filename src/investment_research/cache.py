import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class ResponseCache:
    def __init__(self, path: str, ttl_seconds: int) -> None:
        self.path = Path(path)
        self.ttl_seconds = max(0, ttl_seconds)

    def _key(self, namespace: str, query: str, model: str) -> str:
        value = f"{namespace}:{model}:{query}".encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    def get(self, namespace: str, query: str, model: str) -> str | None:
        if self.ttl_seconds == 0:
            return None

        try:
            with self.path.open(encoding="utf-8") as cache_file:
                entries: dict[str, dict[str, Any]] = json.load(cache_file)
            entry = entries.get(self._key(namespace, query, model))
            if not entry or time.time() - float(entry["created_at"]) >= self.ttl_seconds:
                return None
            response = entry.get("response")
            return response if isinstance(response, str) else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def set(self, namespace: str, query: str, model: str, response: str) -> None:
        if self.ttl_seconds == 0:
            return

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            entries: dict[str, dict[str, Any]] = {}
            if self.path.exists():
                try:
                    with self.path.open(encoding="utf-8") as cache_file:
                        loaded = json.load(cache_file)
                    if isinstance(loaded, dict):
                        entries = loaded
                except (OSError, ValueError, TypeError):
                    entries = {}

            entries[self._key(namespace, query, model)] = {
                "created_at": time.time(),
                "response": response,
            }
            temporary_path: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.path.parent,
                    prefix=f"{self.path.name}.",
                    delete=False,
                ) as temporary_file:
                    json.dump(entries, temporary_file)
                    temporary_path = temporary_file.name
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)
        except OSError:
            return


def response_text(response: Any) -> str | None:
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    return content if isinstance(content, str) else None
