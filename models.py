from dataclasses import dataclass, field
from typing import List

@dataclass
class VehicleCard:
    id: str
    name: str
    cost_ep: int
    crew: int
    brand: int = 0
    technik: int = 0
    hoehe: int = 0
    gefahrgut: int = 0
    text: str = ""

@dataclass
class Player:
    name: str
    ep: int = 6
    crew: int = 5
    hand: List[VehicleCard] = field(default_factory=list)
