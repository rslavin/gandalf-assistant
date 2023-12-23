from enum import Enum


class Role(Enum):
    SYSTEM = 1
    USER = 2
    ASSISTANT = 3

    def __str__(self):
        return self.name.lower()
