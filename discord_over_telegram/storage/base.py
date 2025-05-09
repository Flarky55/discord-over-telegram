from abc import ABC, abstractmethod
from typing import Any


class BaseStorage(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any):
        pass

    @abstractmethod
    def close(self):
        pass

    def set_bidirectional(self, key: str, value: str):
        self.set(key, value)
        self.set(value, key)