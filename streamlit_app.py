from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# -----------------------------
# Data model (MVP)
# -----------------------------

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
class PlayerState:
    pid: str
    name: str
    ep: int = 6
    crew: int = 5
    hand: List[VehicleCard] = field(default_factory=list)

@dataclass
class RoomState:
    room_code: str
    players: Dict[str, PlayerState] = field(default_factory=dict)
    sockets: Dict[str, WebSocket] = field(default_factory=dict)
    turn_order: List[str] = field(default_factory=list)
    active_idx: int = 0
    round_no: int = 1
    started: bool = False

    # very small prototype deck pool
    deck: List[VehicleCard] = field(default_factory=list)
    discard: List[VehicleCard] = field(default_factory=list)

    def active_pid(self) -> Optional[str]:
        if not self.turn_order:
            return None
        return self.turn_order[self.active_idx % len(self.turn_order)]

rooms: Dict[str, RoomState] = {}
rooms_lock = asyncio.Lock()

def sample_deck() -> List[VehicleCard]:
    # MVP: 10 cards from our earlier reference set (duplicates can be added later)
    cards = [
        VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3, text="+1 Technik bei Verkehrsunfall"),
        VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1, text="+1 Brand wenn weiteres Löschfahrzeug beteiligt"),
        VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1, text="Pflicht bei Hochhausbrand (später in Regel)"),
        VehicleCard("V004", "RW", 4, 1, technik=5, text="Zählt doppelt bei eingeklemmter Person (später)"),
        VehicleCard("V005", "ELW 1", 2, 1, text="1x pro Einsatz: -1 EP Kosten (später)"),
        VehicleCard("V006", "GW-Gefahrgut", 4, 1, gefahrgut=5, text="Verhindert Eskalation bei Gefahrgut (später)"),
        VehicleCard("V007", "TM 50", 4, 1, hoehe=5, text="Kann DLK ersetzen (später)"),
        VehicleCard("V008", "GW-Atemschutz", 3, 1, brand=0, text="Support: verhindert Personalverlust (später)"),
        VehicleCard("V009", "Feuerwehrkran", 5, 1, technik=6, text="Pflicht bei Bauunfall (später)"),
        VehicleCard("V010", "WLF", 3, 1, text="Aktivierung +1 EP: kopiert Rolle eines GW (später)"),
    ]
    # For MVP add some duplicates so drawing works
    return cards * 3

def to_public_state(room: RoomState) -> dict:
    # send only what each client should generally know; hand is private -> we send per-client
    return {
        "room_code": room.room_code,
        "started": room.started,
        "round_no": room.round_no,
        "active_pid": room.active_pid(),
        "players": [
            {"pid": p.pid, "name": p.name, "ep": p.ep, "crew": p.crew, "hand_size": len(p.hand)}
            for p in room.players.values()
        ],
    }

async def send(ws: WebSocket, msg: dict) -> None:
    await ws.send_text(json.dumps(msg, ensure_ascii=False))

async def broadcast(room: RoomState, msg: dict) -> None:
    for ws in list(room.sockets.values()):
        await send(ws, msg)

def draw(room: RoomState) -> VehicleCard:
    if not room.deck:
        # reshuffle discard for MVP
        room.deck = room.discard
        room.discard = []
    # simple pop
    return room.deck.pop()

async def sync_room(room: RoomState) -> None:
    await broadcast(room, {"type": "room_state", "state": to_public_state(room)})

async def sync_private(room: RoomState, pid: str) -> None:
    ws = room.sockets.get(pid)
    if not ws:
        return
    player = room.players[pid]
    await send(ws, {
        "type": "private_state",
        "hand": [card.__dict__ for card in player.hand],
        "you": {"pid": player.pid, "name": player.name, "ep": player.ep, "crew": player.crew},
    })

# -----------------------------
# Game actions (MVP)
# -----------------------------

def start_game(room: RoomState) -> None:
    room.started = True
    room.turn_order = list(room.players.keys())
    room.active_idx = 0
    room.round_no = 1

    # build deck and "shuffle"
    room.deck = sample_deck()
    secrets.SystemRandom().shuffle(room.deck)

    # deal 5 vehicle cards each (MVP uses vehicle deck only)
    for p in room.players.values():
        p.ep = 6
        p.crew = 5
        p.hand = [draw(room) for _ in range(5)]

def resources_phase(player: PlayerState) -> None:
    # v1.1: +2 EP (cap 10), +1 crew (cap 7)
    player.ep = min(10, player.ep + 2)
    player.crew = min(7, player.crew + 1)

# -----------------------------
# WebSocket endpoint
# -----------------------------

@app.websocket("/ws/{room_code}/{player_name}")
async def ws_endpoint(ws: WebSocket, room_code: str, player_name: str):
    await ws.accept()
    pid = secrets.token_hex(4)

    async with rooms_lock:
        room = rooms.get(room_code)
        if room is None:
            room = RoomState(room_code=room_code)
            rooms[room_code] = room

        # limit for MVP: 2 players
        if len(room.players) >= 2:
            await send(ws, {"type": "error", "message": "Room ist voll (MVP: max 2 Spieler)."})
            await ws.close()
            return

        room.players[pid] = PlayerState(pid=pid, name=player_name)
        room.sockets[pid] = ws

    await send(ws, {"type": "welcome", "pid": pid, "room_code": room_code})
    await sync_room(room)
    await sync_private(room, pid)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")

            # Basic validation
            if pid not in room.players:
                await send(ws, {"type": "error", "message": "Unbekannter Spieler."})
                continue

            player = room.players[pid]

            # Hostless start: first player can start once 2 players present
            if mtype == "start":
                if room.started:
                    await send(ws, {"type": "error", "message": "Spiel läuft bereits."})
                    continue
                if len(room.players) < 2:
                    await send(ws, {"type": "error", "message": "Warte auf zweiten Spieler."})
                    continue
                start_game(room)
                await broadcast(room, {"type": "info", "message": "Spiel gestartet."})
                await sync_room(room)
                for p in room.players.keys():
                    await sync_private(room, p)
                continue

            # Turn check for action types
            if mtype in {"end_turn", "play_vehicle", "draw"}:
                if not room.started:
                    await send(ws, {"type": "error", "message": "Spiel ist noch nicht gestartet."})
                    continue
                if room.active_pid() != pid:
                    await send(ws, {"type": "error", "message": "Nicht Ihr Zug."})
                    continue

            if mtype == "draw":
                # MVP: draw 1 vehicle card
                player.hand.append(draw(room))
                await send(ws, {"type": "info", "message": "1 Karte gezogen."})
                await sync_private(room, pid)
                continue

            if mtype == "play_vehicle":
                card_id = msg.get("card_id")
                if not card_id:
                    await send(ws, {"type": "error", "message": "card_id fehlt."})
                    continue

                idx = next((i for i, c in enumerate(player.hand) if c.id == card_id), None)
                if idx is None:
                    await send(ws, {"type": "error", "message": "Karte nicht auf der Hand."})
                    continue

                card = player.hand[idx]
                if player.ep < card.cost_ep:
                    await send(ws, {"type": "error", "message": "Nicht genug EP."})
                    continue
                if player.crew < card.crew:
                    await send(ws, {"type": "error", "message": "Nicht genug Personal."})
                    continue

                # MVP: playing a vehicle just spends resources and discards the card
                player.ep -= card.cost_ep
                player.crew -= card.crew
                played = player.hand.pop(idx)
                room.discard.append(played)

                await broadcast(room, {
                    "type": "info",
                    "message": f"{player.name} spielt {played.name} (MVP: Ressourcenverbrauch)."
                })
                await sync_room(room)
                for p in room.players.keys():
                    await sync_private(room, p)
                continue

            if mtype == "end_turn":
                # advance turn, run resources phase for next active player
                room.active_idx = (room.active_idx + 1) % len(room.turn_order)
                # new round if looped
                if room.active_idx == 0:
                    room.round_no += 1

                next_pid = room.active_pid()
                if next_pid:
                    resources_phase(room.players[next_pid])

                await broadcast(room, {"type": "info", "message": "Zug beendet."})
                await sync_room(room)
                for p in room.players.keys():
                    await sync_private(room, p)
                continue

            await send(ws, {"type": "error", "message": f"Unbekannter Nachrichtentyp: {mtype}"})

    except WebSocketDisconnect:
        async with rooms_lock:
            if room_code in rooms:
                room = rooms[room_code]
                room.players.pop(pid, None)
                room.sockets.pop(pid, None)
                # cleanup
                if not room.players:
                    rooms.pop(room_code, None)
    except Exception as e:
        await send(ws, {"type": "error", "message": f"Serverfehler: {e}"})
        await ws.close()
