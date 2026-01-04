import streamlit as st
import os
import random
import sqlite3
import time
import json
import secrets
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Berliner Feuerwehr TCG", layout="wide")

DB_PATH = os.environ.get("BFTCG_DB", "bftcg.sqlite3")
START_COINS = 250

BOOSTER_COST = {"feuer": 25, "rd": 25, "thl": 25}
AXES = ["brand", "technik", "hoehe", "rettung", "koord"]


# =========================================================
# DB
# =========================================================

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        coins INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL DEFAULT 0
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_cards(
        user_id INTEGER NOT NULL,
        card_code TEXT NOT NULL,
        qty INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, card_code)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS decks(
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL DEFAULT 'Standard',
        size INTEGER NOT NULL DEFAULT 40
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deck_cards(
        user_id INTEGER NOT NULL,
        card_code TEXT NOT NULL,
        qty INTEGER NOT NULL,
        PRIMARY KEY(user_id, card_code)
    )""")

    # Duellräume / Match State (All-in-One)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms(
        room_code TEXT PRIMARY KEY,
        host_user_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS room_players(
        room_code TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        joined_at INTEGER NOT NULL,
        PRIMARY KEY(room_code, user_id)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches(
        room_code TEXT PRIMARY KEY,
        state_json TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )""")

    con.commit()
    con.close()


init_db()


# =========================================================
# MODELS
# =========================================================

@dataclass
class VehicleCard:
    code: str
    name: str
    cost_ep: int
    crew: int
    brand: int = 0
    technik: int = 0
    hoehe: int = 0
    rettung: int = 0
    koord: int = 0
    rarity: str = "C"
    theme: str = "feuer"  # feuer | rd | thl
    weight: int = 10
    weakness: str = ""
    art_path: str = ""

    def stats(self) -> Dict[str, int]:
        return {k: int(getattr(self, k)) for k in AXES}


@dataclass
class IncidentCard:
    code: str
    name: str
    ew: int
    time_left: int
    req: Dict[str, int]
    tags: List[str]
    art_path: str = ""


# =========================================================
# CATALOG
# =========================================================

def vehicle_catalog() -> List[VehicleCard]:
    # Codes must match your image filenames in assets/cards/vehicles/<CODE>.png
    return [
        VehicleCard("V100", "LHF", 3, 1, brand=4, technik=1, weakness="Erste Hilfe", theme="feuer", rarity="C", weight=18,
                    art_path="assets/cards/vehicles/V100.png"),
        VehicleCard("V101", "TLF", 4, 1, brand=5, technik=1, weakness="Koordinierung", theme="feuer", rarity="U", weight=10,
                    art_path="assets/cards/vehicles/V101.png"),
        VehicleCard("V102", "DLK 23/12", 3, 1, hoehe=4, brand=1, weakness="Technik", theme="feuer", rarity="U", weight=10,
                    art_path="assets/cards/vehicles/V102.png"),
        VehicleCard("V103", "SW", 3, 1, brand=2, koord=1, weakness="Gefahrgut", theme="feuer", rarity="C", weight=14,
                    art_path="assets/cards/vehicles/V103.png"),

        VehicleCard("V104", "Feuerwehrkran", 5, 1, technik=6, weakness="Koordinierung", theme="thl", rarity="R", weight=3,
                    art_path="assets/cards/vehicles/V104.png"),
        VehicleCard("V105", "ELW 1", 2, 1, koord=3, weakness="Brand", theme="thl", rarity="C", weight=14,
                    art_path="assets/cards/vehicles/V105.png"),
        VehicleCard("V106", "ELW 2", 3, 1, koord=5, weakness="Rettung", theme="thl", rarity="R", weight=3,
                    art_path="assets/cards/vehicles/V106.png"),

        VehicleCard("V108", "RTW", 2, 1, rettung=3, weakness="Feuer", theme="rd", rarity="C", weight=22,
                    art_path="assets/cards/vehicles/V108.png"),
        VehicleCard("V109", "NEF", 2, 1, rettung=2, koord=1, weakness="Technik", theme="rd", rarity="C", weight=18,
                    art_path="assets/cards/vehicles/V109.png"),
        VehicleCard("V110", "ITW", 4, 1, rettung=5, weakness="Koordinierung", theme="rd", rarity="U", weight=8,
                    art_path="assets/cards/vehicles/V110.png"),
        VehicleCard("V111", "RTH", 4, 1, rettung=4, hoehe=1, weakness="Gefahrgut", theme="rd", rarity="U", weight=8,
                    art_path="assets/cards/vehicles/V111.png"),
        VehicleCard("V112", "ITH", 5, 1, rettung=5, hoehe=1, weakness="Brand", theme="rd", rarity="R", weight=3,
                    art_path="assets/cards/vehicles/V112.png"),
    ]


def incident_catalog() -> List[IncidentCard]:
    # Codes must match your image filenames in assets/cards/incidents/<CODE>.png
    return [
        IncidentCard("E001", "Großbrand", ew=3, time_left=2, req={"brand": 6}, tags=["feuer", "gross"],
                     art_path="assets/cards/incidents/E001.png"),
        IncidentCard("E002", "Wohnungsbrand", ew=3, time_left=2, req={"brand": 5}, tags=["feuer"],
                     art_path="assets/cards/incidents/E002.png"),
        IncidentCard("E003", "Verkehrsunfall (eingeklemmt)", ew=3, time_left=2, req={"technik": 4}, tags=["thl", "vu"],
                     art_path="assets/cards/incidents/E003.png"),
        IncidentCard("E004", "Gefahrgutunfall", ew=4, time_left=2, req={"technik": 3}, tags=["feuer", "gefahrgut"],
                     art_path="assets/cards/incidents/E004.png"),

        IncidentCard("E101", "Reanimation", ew=3, time_left=2, req={"rettung": 4}, tags=["rd"],
                     art_path="assets/cards/incidents/E101.png"),
        IncidentCard("E102", "Polytrauma", ew=4, time_left=2, req={"rettung": 5}, tags=["rd"],
                     art_path="assets/cards/incidents/E102.png"),
        IncidentCard("E103", "MANV (klein)", ew=5, time_left=3, req={"rettung": 7, "koord": 3}, tags=["rd", "gross"],
                     art_path="assets/cards/incidents/E103.png"),
    ]


CATALOG = {c.code: c for c in vehicle_catalog()}
INCIDENTS = incident_catalog()


# =========================================================
# STARTER DECKS (40 Karten)
# =========================================================

def starter_decks() -> Dict[str, Dict[str, int]]:
    # totals must be 40
    return {
        "Brandbekämpfung": {
            "V100": 16,  # LHF
            "V101": 8,   # TLF
            "V102": 8,   # DLK
            "V103": 8,   # SW
        },
        "Notfallrettung": {
            "V108": 18,  # RTW
            "V109": 12,  # NEF
            "V110": 6,   # ITW
            "V111": 4,   # RTH
        },
        "Technische Hilfe": {
            "V104": 6,   # Kran
            "V105": 14,  # ELW1
            "V103": 10,  # SW (Logistik)
            "V100": 10,  # LHF (unterstützend)
        },
    }


def validate_deck_40(deck: Dict[str, int]) -> None:
    total = sum(int(v) for v in deck.values())
    if total != 40:
        raise RuntimeError(f"Deck ist nicht 40 Karten (ist {total}).")
    for code in deck.keys():
        if code not in CATALOG:
            raise RuntimeError(f"Deck enthält unbekannte Karte: {code}")


# =========================================================
# COLLECTION / DECK HELPERS
# =========================================================

def add_cards_to_user(con: sqlite3.Connection, user_id: int, card_code: str, qty: int) -> None:
    row = con.execute(
        "SELECT qty FROM user_cards WHERE user_id=? AND card_code=?",
        (user_id, card_code),
    ).fetchone()
    if row:
        con.execute(
            "UPDATE user_cards SET qty=qty+? WHERE user_id=? AND card_code=?",
            (qty, user_id, card_code),
        )
    else:
        con.execute(
            "INSERT INTO user_cards(user_id, card_code, qty) VALUES (?, ?, ?)",
            (user_id, card_code, qty),
        )


def grant_starter_deck(con: sqlite3.Connection, user_id: int, deck_name: str) -> None:
    decks = starter_decks()
    if deck_name not in decks:
        raise RuntimeError("Unbekanntes Starterdeck.")
    deck = decks[deck_name]
    validate_deck_40(deck)

    for code, qty in deck.items():
        add_cards_to_user(con, user_id, code, int(qty))

    con.execute("INSERT OR REPLACE INTO decks(user_id, name, size) VALUES (?, ?, ?)", (user_id, deck_name, 40))
    con.execute("DELETE FROM deck_cards WHERE user_id=?", (user_id,))
    for code, qty in deck.items():
        con.execute("INSERT INTO deck_cards(user_id, card_code, qty) VALUES (?, ?, ?)", (user_id, code, int(qty)))


def get_collection(user_id: int) -> Dict[str, int]:
    con = db()
    rows = con.execute("SELECT card_code, qty FROM user_cards WHERE user_id=? ORDER BY card_code", (user_id,)).fetchall()
    con.close()
    return {r["card_code"]: int(r["qty"]) for r in rows}


def get_deck(user_id: int) -> Dict[str, int]:
    con = db()
    rows = con.execute("SELECT card_code, qty FROM deck_cards WHERE user_id=? ORDER BY card_code", (user_id,)).fetchall()
    con.close()
    return {r["card_code"]: int(r["qty"]) for r in rows}


def get_deck_name(user_id: int) -> str:
    con = db()
    row = con.execute("SELECT name FROM decks WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row["name"] if row else "Kein Deck"


def save_custom_deck(user_id: int, deck_name: str, cards: Dict[str, int]) -> Tuple[bool, str]:
    deck_name = (deck_name or "Eigenes Deck").strip() or "Eigenes Deck"

    total = sum(int(v) for v in cards.values() if int(v) > 0)
    if total != 40:
        return False, f"Deck muss exakt 40 Karten haben (aktuell {total})."

    owned = get_collection(user_id)
    for code, qty in cards.items():
        q = int(qty)
        if q < 0:
            return False, "Negative Mengen sind nicht erlaubt."
        if q > 0 and owned.get(code, 0) < q:
            return False, f"Nicht genug Kopien für {code}: benötigt {q}, vorhanden {owned.get(code, 0)}"
        if q > 0 and code not in CATALOG:
            return False, f"Unbekannte Karte im Deck: {code}"

    con = db()
    try:
        con.execute("INSERT OR REPLACE INTO decks(user_id, name, size) VALUES (?, ?, ?)", (user_id, deck_name, 40))
        con.execute("DELETE FROM deck_cards WHERE user_id=?", (user_id,))
        for code, qty in cards.items():
            q = int(qty)
            if q > 0:
                con.execute("INSERT INTO deck_cards(user_id, card_code, qty) VALUES (?, ?, ?)", (user_id, code, q))
        con.commit()
        return True, "Deck gespeichert."
    except Exception as e:
        return False, f"Speichern fehlgeschlagen: {e}"
    finally:
        con.close()


def deck_to_list(deck: Dict[str, int]) -> List[str]:
    cards: List[str] = []
    for code, qty in deck.items():
        cards.extend([code] * int(qty))
    return cards


# =========================================================
# AUTH
# =========================================================

def register_user(username: str, password: str, starter_deck_name: str) -> Tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Bitte einen Username eingeben."
    if not password or len(password) < 4:
        return False, "Passwort muss mindestens 4 Zeichen haben."

    con = db()
    try:
        now = int(time.time())
        con.execute(
            "INSERT INTO users(username, password, coins, created_at) VALUES (?,?,?,?)",
            (username, password, START_COINS, now),
        )
        user_id = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]

        grant_starter_deck(con, int(user_id), starter_deck_name)

        con.commit()
        return True, "Registrierung erfolgreich. Starterdeck wurde vergeben."
    except sqlite3.IntegrityError:
        return False, "Username existiert bereits."
    except Exception as e:
        return False, f"Registrierung fehlgeschlagen: {e}"
    finally:
        con.close()


def login_user(username: str, password: str) -> Optional[dict]:
    con = db()
    row = con.execute(
        "SELECT id, username, coins FROM users WHERE username=? AND password=?",
        (username.strip(), password),
    ).fetchone()
    con.close()
    if not row:
        return None
    return {"user_id": int(row["id"]), "username": row["username"], "coins": int(row["coins"])}


def refresh_user(user_id: int) -> dict:
    con = db()
    row = con.execute("SELECT id, username, coins FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    return {"user_id": int(row["id"]), "username": row["username"], "coins": int(row["coins"])}


# =========================================================
# BOOSTER
# =========================================================

def roll_rarity_for_slot(slot: int) -> str:
    if slot < 4:
        return "C"
    return "R" if random.random() < 0.20 else "U"


def pick_card(theme: str, rarity: str) -> VehicleCard:
    pool = [c for c in CATALOG.values() if c.theme == theme and c.rarity == rarity]
    if not pool:
        pool = [c for c in CATALOG.values() if c.theme == theme]
    weights = [max(1, int(c.weight)) for c in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def open_booster(theme: str) -> List[VehicleCard]:
    return [pick_card(theme, roll_rarity_for_slot(i)) for i in range(5)]


def buy_open_booster(user_id: int, theme: str) -> Tuple[bool, str, Optional[List[VehicleCard]]]:
    theme = theme.strip().lower()
    if theme not in BOOSTER_COST:
        return False, "Ungültiges Booster-Theme.", None

    con = db()
    user = con.execute("SELECT coins FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        con.close()
        return False, "User nicht gefunden.", None

    cost = int(BOOSTER_COST[theme])
    if int(user["coins"]) < cost:
        con.close()
        return False, "Nicht genug Coins.", None

    cards = open_booster(theme)

    con.execute("UPDATE users SET coins=coins-? WHERE id=?", (cost, user_id))
    for c in cards:
        add_cards_to_user(con, user_id, c.code, 1)

    con.commit()
    con.close()
    return True, "Booster geöffnet.", cards


# =========================================================
# DUEL SYSTEM (Rooms + Match State)
# =========================================================

def room_create(user_id: int, custom_code: str = "") -> Tuple[bool, str, Optional[str]]:
    code = (custom_code or "").strip().upper()
    if not code:
        code = secrets.token_hex(3).upper()

    con = db()
    exists = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (code,)).fetchone()
    if exists:
        con.close()
        return False, "Raumcode existiert bereits.", None

    now = int(time.time())
    con.execute("INSERT INTO rooms(room_code, host_user_id, created_at) VALUES (?, ?, ?)", (code, user_id, now))
    con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, user_id, now))
    con.commit()
    con.close()
    return True, "Raum erstellt.", code


def room_join(user_id: int, room_code: str) -> Tuple[bool, str]:
    code = room_code.strip().upper()
    con = db()
    room = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (code,)).fetchone()
    if not room:
        con.close()
        return False, "Raum nicht gefunden."

    now = int(time.time())
    try:
        con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, user_id, now))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()
    return True, "Raum beigetreten."


def room_status(room_code: str) -> dict:
    code = room_code.strip().upper()
    con = db()
    room = con.execute("SELECT * FROM rooms WHERE room_code=?", (code,)).fetchone()
    if not room:
        con.close()
        raise RuntimeError("Room not found")

    players = con.execute("""
        SELECT u.id, u.username FROM room_players rp
        JOIN users u ON u.id = rp.user_id
        WHERE rp.room_code=?
        ORDER BY rp.joined_at
    """, (code,)).fetchall()

    match = con.execute("SELECT * FROM matches WHERE room_code=?", (code,)).fetchone()
    con.close()

    return {
        "room_code": code,
        "players": [{"id": int(p["id"]), "username": p["username"]} for p in players],
        "match_started": bool(match),
    }


def match_save(room_code: str, state: dict) -> None:
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO matches(room_code, state_json, updated_at) VALUES (?, ?, ?)",
        (room_code, json.dumps(state), int(time.time()))
    )
    con.commit()
    con.close()


def match_load(room_code: str) -> dict:
    con = db()
    row = con.execute("SELECT state_json FROM matches WHERE room_code=?", (room_code,)).fetchone()
    con.close()
    if not row:
        raise RuntimeError("Match not found")
    return json.loads(row["state_json"])


def requirements_met(req: Dict[str, int], totals: Dict[str, int]) -> bool:
    for k, v in req.items():
        if totals.get(k, 0) < int(v):
            return False
    return True


def apply_resources(state: dict, user_id: int) -> None:
    p = state["players"][str(user_id)]
    pressure = int(state["pressure"])
    p["ep"] = min(10, int(p["ep"]) + 2)
    regen = 1
    if pressure >= 8:
        regen = max(0, regen - 1)
    p["crew"] = min(7, int(p["crew"]) + regen)


def draw_from_pile(state: dict, user_id: int, n: int) -> List[str]:
    uid = str(user_id)
    pile = state["players"][uid]["draw_pile"]
    hand = state["players"][uid]["hand"]
    drawn = []
    for _ in range(n):
        if not pile:
            break
        drawn.append(pile.pop())
    hand.extend(drawn)
    return drawn


def end_of_full_round_winner(state: dict) -> Optional[int]:
    gains = {}
    for uid_str, pdata in state["players"].items():
        prev = int(state["round_ew_snapshot"].get(uid_str, 0))
        gains[uid_str] = int(pdata["ew"]) - prev
    max_gain = max(gains.values()) if gains else 0
    winners = [uid for uid, g in gains.items() if g == max_gain and g > 0]
    if len(winners) == 1:
        return int(winners[0])
    return None


def add_coins(user_id: int, amount: int) -> None:
    con = db()
    con.execute("UPDATE users SET coins=coins+? WHERE id=?", (amount, user_id))
    con.commit()
    con.close()


def get_deck_list_or_raise(user_id: int) -> List[str]:
    deck = get_deck(user_id)
    validate_deck_40(deck)
    cards = deck_to_list(deck)
    random.shuffle(cards)
    return cards


def new_match_state(p1_id: int, p2_id: int, deck1: List[str], deck2: List[str]) -> dict:
    inc1 = asdict(random.choice(INCIDENTS))
    inc2 = asdict(random.choice(INCIDENTS))

    draw1 = deck1[:]
    draw2 = deck2[:]
    hand1 = []
    hand2 = []
    for _ in range(10):
        hand1.append(draw1.pop())
        hand2.append(draw2.pop())

    return {
        "version": "duel_mvp0.1",
        "round_no": 1,
        "phase": "planung",
        "pressure": 0,
        "pressure_max": 12,
        "active_player": p1_id,
        "players": {
            str(p1_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand1, "draw_pile": draw1},
            str(p2_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand2, "draw_pile": draw2},
        },
        "open_incidents": [inc1, inc2],
        "assignments": {"0": [], "1": []},  # list of {"user_id":..., "card_code":...}
        "assigned_this_turn": {str(p1_id): False, str(p2_id): False},
        "round_ew_snapshot": {str(p1_id): 0, str(p2_id): 0},
        "log": [],
    }


def match_start(room_code: str) -> Tuple[bool, str]:
    status = room_status(room_code)
    if len(status["players"]) != 2:
        return False, "MVP: Genau 2 Spieler im Raum erforderlich."

    p1_id = status["players"][0]["id"]
    p2_id = status["players"][1]["id"]

    # Decks müssen valide sein (40)
    try:
        deck1 = get_deck_list_or_raise(p1_id)
        deck2 = get_deck_list_or_raise(p2_id)
    except Exception as e:
        return False, f"Deck-Fehler: {e}"

    state = new_match_state(p1_id, p2_id, deck1, deck2)
    match_save(room_code, state)
    return True, "Match gestartet."


def match_assign(room_code: str, user_id: int, slot: int, card_code: str) -> Tuple[bool, str]:
    state = match_load(room_code)

    if state["phase"] != "planung":
        return False, "Zuweisen nur in Planungsphase."
    if int(state["active_player"]) != int(user_id):
        return False, "Nicht dein Zug."

    slot = int(slot)
    if slot not in [0, 1]:
        return False, "Ungültiger Slot."

    uid_str = str(user_id)
    if state["assigned_this_turn"].get(uid_str, False):
        return False, "Bereits diese Runde zugewiesen (MVP-Regel)."

    hand = state["players"][uid_str]["hand"]
    if card_code not in hand:
        return False, "Karte nicht auf der Hand."

    card = CATALOG.get(card_code)
    if not card:
        return False, "Unbekannte Karte."

    pressure = int(state["pressure"])
    cost = int(card.cost_ep) + (1 if pressure >= 5 else 0)

    if int(state["players"][uid_str]["ep"]) < cost:
        return False, f"Nicht genug EP (benötigt {cost})."
    if int(state["players"][uid_str]["crew"]) < int(card.crew):
        return False, "Nicht genug Personal."

    state["players"][uid_str]["ep"] -= cost
    state["players"][uid_str]["crew"] -= int(card.crew)
    hand.remove(card_code)

    state["assignments"][str(slot)].append({"user_id": user_id, "card_code": card_code})
    state["assigned_this_turn"][uid_str] = True
    state["log"].append(f"{user_id} weist {card.name} Slot {slot+1} zu (Kosten {cost} EP).")

    match_save(room_code, state)
    return True, "Zugewiesen."


def resolve_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        req = inc["req"]
        assigned = state["assignments"][str(slot_idx)]

        totals = {k: 0 for k in AXES}
        contrib = {}  # uid -> power

        for a in assigned:
            c = CATALOG[a["card_code"]]
            for k in AXES:
                totals[k] += int(getattr(c, k))
            uid = str(a["user_id"])
            contrib[uid] = contrib.get(uid, 0) + sum(int(getattr(c, k)) for k in AXES)

        ok = requirements_met(req, totals)
        state["log"].append(f"Resolve Slot {slot_idx+1} '{inc['name']}': req={req} totals={totals}")

        if ok:
            if contrib:
                winner_uid = max(contrib.items(), key=lambda x: x[1])[0]
                state["players"][winner_uid]["ew"] += int(inc["ew"])
                state["log"].append(f"Erfüllt. Sieger {winner_uid} erhält {inc['ew']} EW.")
            # replace incident
            state["open_incidents"][slot_idx] = asdict(random.choice(INCIDENTS))
        else:
            state["log"].append("Nicht erfüllt. Eskalation folgt.")

        state["assignments"][str(slot_idx)] = []


def escalate_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        inc["time_left"] = int(inc["time_left"]) - 1
        state["pressure"] = int(state["pressure"]) + 1

        if int(inc["time_left"]) <= 0:
            # increase requirements
            for k, v in list(inc["req"].items()):
                if int(v) > 0:
                    inc["req"][k] = int(v) + 1
            extra = 2 if any(t in inc.get("tags", []) for t in ["gross", "vu", "gefahrgut", "hoehe"]) else 1
            state["pressure"] = int(state["pressure"]) + extra
            inc["time_left"] = 2
            state["log"].append(f"Eskalation Slot {slot_idx+1}: req+1, Druck +{extra}, time reset=2.")


def match_advance_phase(room_code: str, user_id: int) -> Tuple[bool, str]:
    state = match_load(room_code)

    if int(state["active_player"]) != int(user_id):
        return False, "Nicht dein Zug."

    phase = state["phase"]

    if phase == "planung":
        state["phase"] = "einsatz"
        state["log"].append("Phase -> Einsatz.")
    elif phase == "einsatz":
        resolve_phase(state)
        state["phase"] = "eskalation"
        state["log"].append("Phase -> Eskalation.")
    elif phase == "eskalation":
        escalate_phase(state)

        pids = list(map(int, state["players"].keys()))
        pids.sort()
        other = pids[0] if int(user_id) == pids[1] else pids[1]
        state["active_player"] = other

        # reset per-turn
        for k in list(state["assigned_this_turn"].keys()):
            state["assigned_this_turn"][k] = False

        apply_resources(state, other)

        # full round check when lower id becomes active again
        if other == pids[0]:
            winner = end_of_full_round_winner(state)
            if winner is not None:
                add_coins(winner, 5)
                state["log"].append(f"Runden-Sieger {winner} erhält +5 Coins.")
                drawn = draw_from_pile(state, winner, 5)
                state["log"].append(f"Runden-Sieger {winner} zieht 5 Karten: {drawn}")

            for uid_str in list(state["players"].keys()):
                state["round_ew_snapshot"][uid_str] = int(state["players"][uid_str]["ew"])
            state["round_no"] = int(state["round_no"]) + 1

        state["phase"] = "planung"
        state["log"].append("Zugwechsel. Phase -> Planung.")
    else:
        return False, "Ungültige Phase."

    match_save(room_code, state)
    return True, "Phase weiter."


# =========================================================
# UI: AUTH
# =========================================================

if "auth" not in st.session_state:
    st.session_state.auth = None
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

with st.sidebar:
    st.header("Account")

    if not st.session_state.auth:
        t_login, t_reg = st.tabs(["Login", "Registrieren"])

        with t_login:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Passwort", type="password", key="login_p")
            if st.button("Login"):
                user = login_user(u, p)
                if not user:
                    st.error("Login fehlgeschlagen.")
                else:
                    st.session_state.auth = user
                    st.rerun()

        with t_reg:
            u2 = st.text_input("Username", key="reg_u")
            p2 = st.text_input("Passwort (min. 4 Zeichen)", type="password", key="reg_p")
            starter = st.selectbox("Starter Deck wählen", list(starter_decks().keys()), key="reg_starter")

            if st.button("Registrieren & Starter Deck erhalten"):
                ok, msg = register_user(u2, p2, starter)
                if ok:
                    st.success(msg)
                    # Auto-login
                    user = login_user(u2, p2)
                    if user:
                        st.session_state.auth = user
                        st.rerun()
                else:
                    st.error(msg)

    else:
        me = refresh_user(int(st.session_state.auth["user_id"]))
        st.session_state.auth["coins"] = me["coins"]

        st.write(f"Angemeldet: **{me['username']}**")
        st.write(f"Coins: **{me['coins']}**")
        st.write(f"Deck: **{get_deck_name(me['user_id'])}**")

        if st.button("Logout"):
            st.session_state.auth = None
            st.session_state.room_code = ""
            st.rerun()


if not st.session_state.auth:
    st.title("Berliner Feuerwehr TCG")
    st.info("Bitte einloggen oder registrieren. Bei Registrierung erhalten Sie ein Starter Deck.")
    st.stop()

user_id = int(st.session_state.auth["user_id"])

# =========================================================
# UI: TABS
# =========================================================

tabs = st.tabs(["Start", "Sammlung", "Booster", "Deck-Editor", "Duell"])

# =========================================================
# START
# =========================================================
with tabs[0]:
    st.title("Berliner Feuerwehr TCG")
    st.markdown("""
**Berliner Feuerwehr TCG** ist ein digitales Sammelkartenspiel mit realistischen Fahrzeugen der Berliner Feuerwehr.

**Kurzregeln (MVP Duell):**
- 2 Spieler im Raum, beide mit einem gültigen **40er Deck**
- Matchstart: Jeder zieht **10 Karten**
- Phasen: **Planung → Einsatz (Resolve) → Eskalation → Zugwechsel**
- In der Planung: 1 Karte pro Zug einem von 2 Einsätzen zuweisen
- Einsätze bringen **Einsatzwert (EW)** bei Erfüllung der Anforderungen
- Nach jeder vollen Runde: Runden-Sieger bekommt **+5 Coins** und zieht **5 Karten**
""")
    st.caption("Hinweis: Ereigniskarten werden als nächster Schritt spielmechanisch aktiviert.")

# =========================================================
# SAMMLUNG
# =========================================================
with tabs[1]:
    st.subheader("Ihre Sammlung")
    coll = get_collection(user_id)

    if not coll:
        st.caption("Noch keine Karten.")
    else:
        def sort_key(code: str):
            c = CATALOG.get(code)
            return (c.theme if c else "z", c.name if c else code)

        for code in sorted(coll.keys(), key=sort_key):
            qty = coll[code]
            card = CATALOG.get(code)
            if not card:
                continue

            st.markdown(f"### {qty}× {card.name} ({card.code})")
            img = f"assets/cards/vehicles/{card.code}.png"
            if os.path.exists(img):
                st.image(img, width=280)

            st.caption(f"EP {card.cost_ep} | Crew {card.crew} | Stats {card.stats()} | Schwäche: {card.weakness}")
            st.divider()

# =========================================================
# BOOSTER
# =========================================================
with tabs[2]:
    st.subheader("Booster öffnen")
    c1, c2, c3 = st.columns(3)

    def open_and_show(theme: str):
        ok, msg, cards = buy_open_booster(user_id, theme)
        if not ok:
            st.error(msg)
            return
        st.success(msg)
        st.session_state.auth = refresh_user(user_id)

        for c in cards:
            st.markdown(f"**{c.name} ({c.code}) – {c.rarity}**")
            img = f"assets/cards/vehicles/{c.code}.png"
            if os.path.exists(img):
                st.image(img, width=240)

    with c1:
        st.markdown("### Feuer")
        st.caption("Fokus: Brand/Höhe/Logistik")
        if st.button("Feuer-Booster (25 Coins)"):
            open_and_show("feuer")

    with c2:
        st.markdown("### Rettungsdienst")
        st.caption("Fokus: Rettung/Koordination")
        if st.button("RD-Booster (25 Coins)"):
            open_and_show("rd")

    with c3:
        st.markdown("### THL")
        st.caption("Fokus: Technik/Koordination")
        if st.button("THL-Booster (25 Coins)"):
            open_and_show("thl")

# =========================================================
# DECK-EDITOR
# =========================================================
with tabs[3]:
    st.subheader("Deck-Editor (40 Karten)")

    coll = get_collection(user_id)
    if not coll:
        st.info("Sie haben noch keine Karten. Öffnen Sie zuerst Booster.")
        st.stop()

    current_deck = get_deck(user_id)
    current_name = get_deck_name(user_id)
    deck_name = st.text_input("Deckname", value=current_name if current_name != "Kein Deck" else "Eigenes Deck")

    st.caption("Regeln: Deckgröße exakt 40. Pro Karte maximal so viele Kopien wie in Ihrer Sammlung.")

    f_theme = st.selectbox("Filter Theme", ["Alle", "feuer", "rd", "thl"], index=0)
    f_text = st.text_input("Suche (Name oder Code)", value="").strip().lower()

    def sort_key(code: str):
        c = CATALOG.get(code)
        if not c:
            return ("z", code)
        return (c.theme, c.name)

    codes = sorted(coll.keys(), key=sort_key)

    filtered = []
    for code in codes:
        card = CATALOG.get(code)
        if not card:
            continue
        if f_theme != "Alle" and card.theme != f_theme:
            continue
        if f_text and (f_text not in card.name.lower()) and (f_text not in card.code.lower()):
            continue
        filtered.append(code)

    new_deck: Dict[str, int] = {}
    total = 0

    st.divider()
    cols = st.columns(3)
    col_idx = 0

    for code in filtered:
        card = CATALOG[code]
        owned_qty = int(coll.get(code, 0))
        default_qty = int(current_deck.get(code, 0))

        with cols[col_idx]:
            st.markdown(f"**{card.name}**  \n`{card.code}` · {card.theme.upper()} · {card.rarity}")
            img = f"assets/cards/vehicles/{card.code}.png"
            if os.path.exists(img):
                st.image(img, use_container_width=True)

            qty = st.number_input(
                "Menge",
                min_value=0,
                max_value=owned_qty,
                value=min(default_qty, owned_qty),
                step=1,
                key=f"deck_qty_{card.code}"
            )

            st.caption(f"Besitz: {owned_qty} | EP {card.cost_ep} | Crew {card.crew} | Schwäche: {card.weakness}")
            if qty > 0:
                new_deck[card.code] = int(qty)
            total += int(qty)

        col_idx = (col_idx + 1) % 3

    st.divider()
    st.info(f"Deckgröße: {total} / 40")

    c_save, c_fill, c_clear = st.columns([1, 1, 1])

    with c_save:
        if st.button("Deck speichern"):
            ok, msg = save_custom_deck(user_id, deck_name, new_deck)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with c_fill:
        if st.button("Auto-Fill (bis 40)"):
            temp = dict(new_deck)
            temp_total = sum(temp.values())
            for code in sorted(coll.keys(), key=sort_key):
                if temp_total >= 40:
                    break
                owned_qty = int(coll[code])
                already = int(temp.get(code, 0))
                if already < owned_qty:
                    add = min(owned_qty - already, 40 - temp_total)
                    if add > 0:
                        temp[code] = already + add
                        temp_total += add
            for k, v in temp.items():
                st.session_state[f"deck_qty_{k}"] = v
            st.rerun()

    with c_clear:
        if st.button("Alles auf 0"):
            for code in filtered:
                st.session_state[f"deck_qty_{code}"] = 0
            st.rerun()

# =========================================================
# DUELL
# =========================================================
with tabs[4]:
    st.subheader("Duellmodus")

    left, right = st.columns([1, 1])

    with left:
        st.markdown("### Raum erstellen")
        custom = st.text_input("Optionaler Raumcode (z. B. BERLIN1)", value="", key="room_custom")
        if st.button("Raum erstellen"):
            ok, msg, code = room_create(user_id, custom)
            if ok:
                st.session_state.room_code = code
                st.success(f"{msg} Code: {code}")
            else:
                st.error(msg)

    with right:
        st.markdown("### Raum beitreten")
        join_code = st.text_input("Raumcode", value=st.session_state.room_code, key="room_join")
        if st.button("Raum beitreten"):
            ok, msg = room_join(user_id, join_code)
            if ok:
                st.session_state.room_code = join_code.strip().upper()
                st.success(msg)
            else:
                st.error(msg)

    if not st.session_state.room_code:
        st.info("Erstellen oder treten Sie einem Raum bei.")
        st.stop()

    st.divider()

    try:
        status = room_status(st.session_state.room_code)
    except Exception as e:
        st.error(str(e))
        st.stop()

    st.write(f"Aktueller Raum: **{status['room_code']}**")
    st.write("Spieler im Raum:")
    for p in status["players"]:
        st.write(f"- {p['username']} (id={p['id']})")

    if st.button("Match starten (2 Spieler + 40er Decks)"):
        ok, msg = match_start(st.session_state.room_code)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.divider()

    # Try load match
    try:
        state = match_load(st.session_state.room_code)
    except Exception:
        st.caption("Noch kein Match gestartet.")
        st.stop()

    # Match UI
    my_id = user_id
    if str(my_id) not in state["players"]:
        st.error("Sie sind nicht Teil dieses Matches.")
        st.stop()

    st.write(f"Runde: {state['round_no']} | Phase: **{state['phase']}** | Druck: {state['pressure']}/{state['pressure_max']}")
    st.write(f"Aktiver Spieler (user_id): **{state['active_player']}**")

    my = state["players"][str(my_id)]
    st.write(f"Sie: EP={my['ep']} | Crew={my['crew']} | EW={my['ew']} | Draw-Pile={len(my['draw_pile'])} | Hand={len(my['hand'])}")

    # Show incidents
    st.markdown("## Offene Einsätze")
    cA, cB = st.columns(2)
    for i, col in enumerate([cA, cB]):
        with col:
            inc = state["open_incidents"][i]
            st.markdown(f"### Slot {i+1}: {inc['name']} (`{inc['code']}`)")
            img = f"assets/cards/incidents/{inc['code']}.png"
            if os.path.exists(img):
                st.image(img, width=320)
            st.write(f"Zeit: {inc['time_left']} | EW: {inc['ew']}")
            st.write("Anforderungen:")
            st.json({k: v for k, v in inc["req"].items() if int(v) > 0})

    st.divider()

    st.markdown("## Ihre Hand (Fahrzeuge)")
    if not my["hand"]:
        st.caption("Keine Karten auf der Hand.")
    else:
        # build labels
        labels = []
        label_to_code = {}
        for code in my["hand"]:
            c = CATALOG.get(code)
            if c:
                label = f"{c.name} ({c.code}) – EP {c.cost_ep} | Crew {c.crew} | {c.stats()}"
            else:
                label = code
            labels.append(label)
            label_to_code[label] = code

        selected_label = st.selectbox("Karte wählen", labels)
        selected_code = label_to_code[selected_label]
        sel = CATALOG.get(selected_code)

        if sel:
            img = f"assets/cards/vehicles/{sel.code}.png"
            if os.path.exists(img):
                st.image(img, width=360)
            st.caption(f"Schwäche: {sel.weakness}")

        slot = st.radio("Slot", [0, 1], horizontal=True)

        if st.button("Zuweisen (nur Planung & wenn Sie dran sind)"):
            ok, msg = match_assign(st.session_state.room_code, my_id, slot, selected_code)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()

    if st.button("Phase weiter"):
        ok, msg = match_advance_phase(st.session_state.room_code, my_id)
        if ok:
            st.success(msg)
            # coins refresh (if you won round)
            st.session_state.auth = refresh_user(my_id)
            st.rerun()
        else:
            st.error(msg)

    with st.expander("Log (letzte 60)"):
        for line in state.get("log", [])[-60:]:
            st.write(line)
