"""Storage interface for uploaded files.

Local disk today; a Cloudflare R2-backed implementation can be swapped in
later (see 00_agent_ground_rules.txt / 06_devops_instructions.txt) without
touching callers, as long as it exposes the same three methods.
"""

import os


class LocalStorage:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _full_path(self, relative_path):
        return os.path.join(self.base_dir, relative_path)

    def write_bytes(self, relative_path, data):
        full_path = self._full_path(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)
        return relative_path

    def read_text(self, relative_path, encoding="utf-8"):
        with open(self._full_path(relative_path), "r", encoding=encoding, errors="replace") as f:
            return f.read()

    def read_bytes(self, relative_path):
        with open(self._full_path(relative_path), "rb") as f:
            return f.read()

    def delete(self, relative_path):
        full_path = self._full_path(relative_path)
        if os.path.isfile(full_path):
            os.remove(full_path)
