import shelve
from .base import BaseStorage
from typing import Any


class ShelveStorage(BaseStorage):
    def __init__(self, filename: str):
        self.shelf = shelve.open(filename)

    def get(self, key: str, default: Any = None):
        return self.shelf.get(key, default)
    
    def set(self, key: str, value: Any):
        self.shelf[key] = value

    def close(self):
        self.shelf.close()