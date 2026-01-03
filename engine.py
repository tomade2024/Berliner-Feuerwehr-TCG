import random
from .models import Player
from .data import VEHICLES

def start_game(player: Player):
    deck = VEHICLES * 3
    random.shuffle(deck)
    player.hand = deck[:5]
    player.ep = 6
    player.crew = 5

def play_vehicle(player: Player, card_id: str):
    card = next((c for c in player.hand if c.id == card_id), None)
    if not card:
        return "Karte nicht gefunden"
    if player.ep < card.cost_ep:
        return "Nicht genug EP"
    if player.crew < card.crew:
        return "Nicht genug Personal"

    player.ep -= card.cost_ep
    player.crew -= card.crew
    player.hand.remove(card)
    return f"{card.name} gespielt"
