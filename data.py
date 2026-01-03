from .models import VehicleCard

VEHICLES = [
    VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3),
    VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1),
    VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1),
    VehicleCard("V004", "RW", 4, 1, technik=5),
    VehicleCard("V005", "ELW 1", 2, 1, text="−1 EP Kosten 1× pro Einsatz"),
]
