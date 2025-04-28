import shelve
from typing import Any


class DatabaseService:
    def __init__(self, filename: str):
        self.shelf = shelve.open(filename)

    def get(self, key: str, default: Any = None):
        return self.shelf.get(key, default)