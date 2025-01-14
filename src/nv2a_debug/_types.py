from __future__ import annotations

from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Register:
    """Holds the state of a single nv2a register."""

    name: str
    x: float = 0
    y: float = 0
    z: float = 0
    w: float = 0

    def to_json(self) -> list:
        return [self.name, self.x, self.y, self.z, self.w]

    def get(self, mask: str) -> list[float]:
        ret = []
        for field in mask:
            if field == "x":
                ret.append(self.x)
            elif field == "y":
                ret.append(self.y)
            elif field == "z":
                ret.append(self.z)
            elif field == "w":
                ret.append(self.w)
            else:
                msg = f"Invalid mask component {field}"
                raise ValueError(msg)
        return ret

    def set(self, mask: str, value: tuple[float, float, float, float]):
        for field in mask:
            if field == "x":
                self.x = value[0]
            elif field == "y":
                self.y = value[1]
            elif field == "z":
                self.z = value[2]
            elif field == "w":
                self.w = value[3]
            else:
                msg = f"Invalid mask component {field}"
                raise ValueError(msg)

    def __str__(self):
        return f"{self.name}[{self.x:f},{self.y:f},{self.z:f},{self.w:f}]"
