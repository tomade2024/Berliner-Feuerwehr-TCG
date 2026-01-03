import os
import json
import time
import random
import secrets
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import streamlit as st

# ==========================================================
# Config
# ==========================================================

DB_PATH = os.environ.get("BFTCG_DB", "bftcg_streamlit.sqlite3")
START_COINS = 250
BOOSTER_COST = {"feuer": 25, "rd": 25, "thl": 25}
AXES = ["brand", "technik", "hoehe", "gefahrgut", "rettung", "koord"]

st.set_page_config(page_title="Berliner Feuerwehr TCG (All-in-One)", layout="wide")
st.title("Berliner Feuerwehr TCG – All-in-One Streamlit (ohne Backend)")

# ==========================================================
# Catalog
# ==========================================================

@dataclass
class VehicleCard:
    code: str
    name: str
    cost_ep: int
    crew: int
    brand: int = 0
    technik: int = 0
    hoehe: int = 0
    gefahrgut: int = 0
    rettung: int = 0
    koord: int = 0
    theme: str = "feuer"     # feuer | rd | thl
    rarity: str = "C"       # C | U | R
    weight: int = 10
    text: str = ""

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
    escalation_text: str = ""


def vehicle_catalog() -> List[VehicleCard]:
    return [
        # FEUER
        VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1, theme="feuer", rarity="C", weight=18, text="Löschfahrzeug."),
        VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3, theme="feuer", rarity="U", weight=10, text="Allround."),
        VehicleCard("V011", "TLF", 4, 1, brand=5, technik=1, theme="feuer", rarity="U", weight=9, text="Tanklöschfahrzeug."),
        VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1, theme="feuer", rarity="U", weight=10, text="Höhenkomponente."),
        VehicleCard("V012", "SW", 3, 1, brand=2, koord=1, theme="feuer", rarity="C", weight=14, text="Wasserversorgung/Logistik."),
        VehicleCard("V006", "GW-Gefahrgut", 4, 1, gefahrgut=5, theme="feuer", rarity="R", weight=4, text="Gefahrgut-Spezialist."),
        VehicleCard("V007", "TM 50", 4, 1, hoehe=5, theme="feuer", rarity="R", weight=4, text="Teleskopmast."),
        VehicleCard("V009", "Feuerwehrkran", 5, 1, technik=6, theme="feuer", rarity="R", weight=3, text="Schwerlast."),
        VehicleCard("V013", "ELW 2", 3, 1, koord=5, theme="feuer", rarity="R", weight=3, text="Führung/Koordination."),

        # THL
        VehicleCard("V004", "RW", 4, 1, technik=5, theme="thl", rarity="U", weight=10, text="Rüstwagen."),
        VehicleCard("V005", "ELW 1", 2, 1, koord=3, theme="thl", rarity="C", weight=14, text="Einsatzleitung (leicht)."),
        VehicleCard("V019", "GW-Rüst", 3, 1, technik=3, theme="thl", rarity="C", weight=16, text="Gerätewagen THL."),
        VehicleCard("V020", "GW-L", 2, 1, technik=1, koord=1, theme="thl", rarity="C", weight=16, text="Logistik."),
        VehicleCard("V021", "VRW", 2, 1, technik=2, theme="thl", rarity="C", weight=14, text="Vorausrüstwagen."),

        # RD
        VehicleCard("V014", "RTW", 2, 1, rettung=3, theme="rd", rarity="C", weight=22, text="Rettungstransportwagen."),
        VehicleCard("V015", "NEF", 2, 1, rettung=2, koord=1, theme="rd", rarity="C", weight=18, text="Notarzt."),
        VehicleCard("V023", "KTW", 1, 1, rettung=1, theme="rd", rarity="C", weight=22, text="Krankentransport."),
        VehicleCard("V016", "ITW", 4, 1, rettung=5, theme="rd", rarity="U", weight=8, text="Intensivtransport."),
        VehicleCard("V017", "RTH", 4, 1, rettung=4, hoehe=1, theme="rd", rarity="U", weight=8, text="Rettungshubschrauber."),
        VehicleCard("V024", "OrgL RD", 2, 1, koord=4, rettung=1, theme="rd", rarity="U", weight=7, text="Koordination RD."),
        VehicleCard("V018", "ITH", 5, 1, rettung=5, hoehe=1, theme="rd", rarity="R", weight=3, text="Intensivtransporthubschrauber."),
    ]


def incident_catalog() -> List[IncidentCard]:
    return [
        # FEUER/THL
        IncidentCard("I001", "Wohnungsbrand", ew=3, time_left=2, req={"brand": 6}, tags=["feuer"], escalation_text="Anforderung +1 Brand, Druck +1"),
        IncidentCard("I002", "VU – eingeklemmte Person", ew=3, time_left=2, req={"technik": 5}, tags=["thl", "vu"], escalation_text="Druck +2"),
        IncidentCard("I003", "Hochhausbrand", ew=5, time_left=3, req={"brand": 5, "hoehe": 4}, tags=["feuer", "hoehe"], escalation_text="Anforderungen +1, Druck +2"),
        IncidentCard("I004", "Gefahrgutunfall", ew=4, time_left=2, req={"gefahrgut": 4}, tags=["feuer", "gefahrgut"], escalation_text="Druck +2"),
        IncidentCard("I005", "Bauunfall", ew=4, time_left=3, req={"technik": 6}, tags=["thl"], escalation_text="Anforderung +1 Technik, Druck +1"),

        # RD
        IncidentCard("R001", "Reanimation", ew=3, time_left=2, req={"rettung": 4}, tags=["rd"], escalation_text="Druck +2"),
        IncidentCard("R002", "Polytrauma", ew=4, time_left=2, req={"rettung": 5}, tags=["rd"], escalation_text="Anforderung +1 Rettung, Druck +2"),
        IncidentCard("R003", "MANV (klein)", ew=5, time_left=3, req={"rettung": 7, "koord": 3}, tags=["rd", "gross"], escalation_text="Druck +2, Anforderungen +1"),
        IncidentCard("R004", "Intensivtransport", ew=5, time_left=3, req={"rettung": 6}, tags=["rd"], escalation_text="Druck +1"),
    ]


CATALOG = {c.code: c for c in vehicle_catalog()}

# ==========================================================
# DB layer
# ==========================================================

def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        coins INTEGER NOT NULL DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_cards (
        user_id INTEGER NOT NULL,
        card_code TEXT NOT NULL,
        qty INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, card_code)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS decks (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL DEFAULT 'Standard',
        size INTEGER NOT NULL DEFAULT 40
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deck_cards (
        user_id INTEGER NOT NULL,
        card_code TEXT NOT NULL,
        qty INTEGER NOT NULL,
        PRIMARY KEY(user_id, card_code)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_code TEXT PRIMARY KEY,
        host_user_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS room_players (
        room_code TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        joined_at INTEGER NOT NULL,
        PRIMARY KEY(room_code, user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        room_code TEXT PRIMARY KEY,
        state_json TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """)

    con.commit()
    con.close()


init_db()

# ==========================================================
# Auth / session helpers
# ==========================================================

def register_user(username: str, password: str) -> Tuple[bool, str]:
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username, password, coins) VALUES (?, ?, ?)",
            (username, password, START_COINS),
        )
        con.commit()
        return True, f"Registriert. Start-Coins: {START_COINS}"
    except sqlite3.IntegrityError:
        return False, "Username existiert bereits."
    finally:
        con.close()


def login_user(username: str, password: str) -> Optional[dict]:
    con = db()
    row = con.execute(
        "SELECT id, username, coins FROM users WHERE username=? AND password=?",
        (username, password),
    ).fetchone()
    con.close()
    if not row:
        return None
    return {"user_id": int(row["id"]), "username": row["username"], "coins": int(row["coins"])}


def get_user(user_id: int) -> dict:
    con = db()
    row = con.execute("SELECT id, username, coins FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    if not row:
        raise RuntimeError("User not found")
    return {"user_id": int(row["id"]), "username": row["username"], "coins": int(row["coins"])}


def add_cards_to_user(user_id: int, codes: List[str]) -> None:
    con = db()
    for code in codes:
        r = con.execute("SELECT qty FROM user_cards WHERE user_id=? AND card_code=?", (user_id, code)).fetchone()
        if r:
            con.execute("UPDATE user_cards SET qty=qty+1 WHERE user_id=? AND card_code=?", (user_id, code))
        else:
            con.execute("INSERT INTO user_cards(user_id, card_code, qty) VALUES (?, ?, 1)", (user_id, code))
    con.commit()
    con.close()


def get_collection(user_id: int) -> List[dict]:
    con = db()
    rows = con.execute("SELECT card_code, qty FROM user_cards WHERE user_id=? ORDER BY card_code", (user_id,)).fetchall()
    con.close()
    out = []
    for r in rows:
        c = CATALOG.get(r["card_code"])
        if c:
            out.append({"code": c.code, "name": c.name, "qty": int(r["qty"]), "theme": c.theme, "rarity": c.rarity})
    return out


def get_deck(user_id: int) -> dict:
    con = db()
    deck = con.execute("SELECT name, size FROM decks WHERE user_id=?", (user_id,)).fetchone()
    rows = con.execute("SELECT card_code, qty FROM deck_cards WHERE user_id=?", (user_id,)).fetchall()
    con.close()
    return {
        "name": deck["name"] if deck else "Standard",
        "size": int(deck["size"]) if deck else 40,
        "cards": {r["card_code"]: int(r["qty"]) for r in rows},
    }


def save_deck(user_id: int, name: str, cards: Dict[str, int]) -> Tuple[bool, str]:
    total = sum(int(v) for v in cards.values() if int(v) > 0)
    if total != 40:
        return False, f"Deck muss exakt 40 Karten haben (aktuell {total})."

    owned = {c["code"]: c["qty"] for c in get_collection(user_id)}
    for code, qty in cards.items():
        q = int(qty)
        if q < 0:
            return False, "Negative Mengen sind nicht erlaubt."
        if q > 0 and owned.get(code, 0) < q:
            return False, f"Nicht genug Kopien für {code}: benötigt {q}, vorhanden {owned.get(code, 0)}"
        if q > 0 and code not in CATALOG:
            return False, f"Unbekannte Karte: {code}"

    con = db()
    con.execute("INSERT OR REPLACE INTO decks(user_id, name, size) VALUES (?, ?, 40)", (user_id, name))
    con.execute("DELETE FROM deck_cards WHERE user_id=?", (user_id,))
    for code, qty in cards.items():
        q = int(qty)
        if q > 0:
            con.execute("INSERT INTO deck_cards(user_id, card_code, qty) VALUES (?, ?, ?)", (user_id, code, q))
    con.commit()
    con.close()
    return True, "Deck gespeichert."


# ==========================================================
# Booster (weighted by theme + rarity + weight)
# ==========================================================

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


def buy_open_booster(user_id: int, theme: str) -> Tuple[bool, str, Optional[dict]]:
    theme = theme.lower().strip()
    if theme not in BOOSTER_COST:
        return False, "Ungültiges Booster-Theme.", None

    user = get_user(user_id)
    cost = BOOSTER_COST[theme]
    if user["coins"] < cost:
        return False, "Nicht genug Coins.", None

    cards = open_booster(theme)
    codes = [c.code for c in cards]

    con = db()
    con.execute("UPDATE users SET coins=coins-? WHERE id=?", (cost, user_id))
    con.commit()
    con.close()

    add_cards_to_user(user_id, codes)
    new_user = get_user(user_id)

    payload = {
        "theme": theme,
        "cost": cost,
        "coins": new_user["coins"],
        "cards": [{"code": c.code, "name": c.name, "theme": c.theme, "rarity": c.rarity} for c in cards],
    }
    return True, "Booster geöffnet.", payload


# ==========================================================
# Rooms / Match
# ==========================================================

def create_room(user_id: int, code: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    room_code = (code or "").strip().upper()
    if not room_code:
        room_code = secrets.token_hex(3).upper()

    con = db()
    exists = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    if exists:
        con.close()
        return False, "Raumcode existiert bereits.", None

    now = int(time.time())
    con.execute("INSERT INTO rooms(room_code, host_user_id, created_at) VALUES (?, ?, ?)", (room_code, user_id, now))
    con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (room_code, user_id, now))
    con.commit()
    con.close()
    return True, "Raum erstellt.", room_code


def join_room(user_id: int, room_code: str) -> Tuple[bool, str]:
    room_code = room_code.strip().upper()
    con = db()
    room = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    if not room:
        con.close()
        return False, "Raum nicht gefunden."

    now = int(time.time())
    try:
        con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (room_code, user_id, now))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()
    return True, "Raum beigetreten."


def room_status(room_code: str) -> dict:
    room_code = room_code.strip().upper()
    con = db()
    room = con.execute("SELECT * FROM rooms WHERE room_code=?", (room_code,)).fetchone()
    if not room:
        con.close()
        raise RuntimeError("Room not found")

    players = con.execute("""
        SELECT u.id, u.username FROM room_players rp
        JOIN users u ON u.id = rp.user_id
        WHERE rp.room_code=?
        ORDER BY rp.joined_at
    """, (room_code,)).fetchall()

    match = con.execute("SELECT room_code FROM matches WHERE room_code=?", (room_code,)).fetchone()
    con.close()

    return {
        "room_code": room_code,
        "players": [{"id": int(p["id"]), "username": p["username"]} for p in players],
        "match_started": bool(match),
    }


def get_deck_list(user_id: int) -> List[str]:
    d = get_deck(user_id)
    cards = []
    for code, qty in d["cards"].items():
        cards.extend([code] * int(qty))
    if len(cards) != 40:
        raise RuntimeError("Kein gültiges 40er-Deck gespeichert.")
    random.shuffle(cards)
    return cards


def new_match_state(p1_id: int, p2_id: int, deck1: List[str], deck2: List[str]) -> dict:
    incs = incident_catalog()
    inc1 = asdict(random.choice(incs))
    inc2 = asdict(random.choice(incs))

    draw1 = deck1[:]
    draw2 = deck2[:]
    hand1 = [draw1.pop() for _ in range(10)]
    hand2 = [draw2.pop() for _ in range(10)]

    return {
        "version": "solo_mvp0.2",
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
        "assignments": {"0": [], "1": []},  # {"user_id":..., "card_code":...}
        "assigned_this_turn": {str(p1_id): False, str(p2_id): False},
        "round_ew_snapshot": {str(p1_id): 0, str(p2_id): 0},
        "log": [],
    }


def save_match(room_code: str, state: dict) -> None:
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO matches(room_code, state_json, updated_at) VALUES (?, ?, ?)",
        (room_code, json.dumps(state), int(time.time()))
    )
    con.commit()
    con.close()


def load_match(room_code: str) -> dict:
    con = db()
    row = con.execute("SELECT state_json FROM matches WHERE room_code=?", (room_code,)).fetchone()
    con.close()
    if not row:
        raise RuntimeError("Match not found")
    return json.loads(row["state_json"])


def start_match(room_code: str) -> Tuple[bool, str]:
    status = room_status(room_code)
    if len(status["players"]) != 2:
        return False, "MVP: Genau 2 Spieler im Raum erforderlich."

    p1_id = status["players"][0]["id"]
    p2_id = status["players"][1]["id"]

    try:
        deck1 = get_deck_list(p1_id)
        deck2 = get_deck_list(p2_id)
    except Exception as e:
        return False, f"Deck-Fehler: {e}"

    state = new_match_state(p1_id, p2_id, deck1, deck2)
    save_match(room_code, state)
    return True, "Match gestartet."


def requirements_met(req: Dict[str, int], totals: Dict[str, int]) -> bool:
    for k, v in req.items():
        if totals.get(k, 0) < int(v):
            return False
    return True


def resolve_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        req = inc["req"]

        assigned = state["assignments"][str(slot_idx)]
        totals = {k: 0 for k in AXES}
        contrib = {}

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
            state["open_incidents"][slot_idx] = asdict(random.choice(incident_catalog()))
        else:
            state["log"].append("Nicht erfüllt. Eskalation folgt.")

        state["assignments"][str(slot_idx)] = []


def escalate_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        inc["time_left"] -= 1
        state["pressure"] += 1

        if inc["time_left"] <= 0:
            for k, v in list(inc["req"].items()):
                if int(v) > 0:
                    inc["req"][k] = int(v) + 1
            extra = 2 if any(t in inc["tags"] for t in ["gross", "vu", "gefahrgut", "hoehe"]) else 1
            state["pressure"] += extra
            inc["time_left"] = 2
            state["log"].append(f"Eskalation Slot {slot_idx+1}: req+1, Druck +{extra}, time reset=2.")


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


def assign_card(room_code: str, user_id: int, slot: int, card_code: str) -> Tuple[bool, str]:
    state = load_match(room_code)

    if int(state["active_player"]) != int(user_id):
        return False, "Nicht dein Zug."
    if state["phase"] != "planung":
        return False, "Zuweisen nur in Planungsphase."

    slot = int(slot)
    if slot not in [0, 1]:
        return False, "Ungültiger Slot."

    uid_str = str(user_id)
    if state["assigned_this_turn"].get(uid_str, False):
        return False, "Bereits zugewiesen (MVP-Regel)."

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
    state["log"].append(f"{get_user(user_id)['username']} weist {card.name} Slot {slot+1} zu (Kosten {cost} EP).")

    save_match(room_code, state)
    return True, "Zugewiesen."


def advance_phase(room_code: str, user_id: int) -> Tuple[bool, str]:
    state = load_match(room_code)

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

        for k in list(state["assigned_this_turn"].keys()):
            state["assigned_this_turn"][k] = False

        apply_resources(state, other)

        if other == pids[0]:
            winner = end_of_full_round_winner(state)
            if winner is not None:
                add_coins(winner, 5)
                state["log"].append(f"Runden-Sieger {winner} erhält +5 Coins.")
                drawn = draw_from_pile(state, winner, 5)
                state["log"].append(f"Runden-Sieger {winner} zieht 5 Karten aus Deck: {drawn}")

            for uid_str in list(state["players"].keys()):
                state["round_ew_snapshot"][uid_str] = int(state["players"][uid_str]["ew"])
            state["round_no"] += 1

        state["phase"] = "planung"
        state["log"].append("Zugwechsel. Phase -> Planung.")
    else:
        return False, "Ungültige Phase."

    save_match(room_code, state)
    return True, "Phase weiter."


# ==========================================================
# UI
# ==========================================================

if "auth" not in st.session_state:
    st.session_state.auth = None
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

with st.sidebar:
    st.header("Account")

    if not st.session_state.auth:
        tab1, tab2 = st.tabs(["Login", "Registrieren"])
        with tab1:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Passwort", type="password", key="login_p")
            if st.button("Login"):
                user = login_user(u, p)
                if not user:
                    st.error("Login fehlgeschlagen.")
                else:
                    st.session_state.auth = user
                    st.success("Eingeloggt.")
                    st.rerun()

        with tab2:
            u2 = st.text_input("Username", key="reg_u")
            p2 = st.text_input("Passwort", type="password", key="reg_p")
            if st.button("Account erstellen"):
                ok, msg = register_user(u2, p2)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
    else:
        me = get_user(int(st.session_state.auth["user_id"]))
        st.write(f"Angemeldet als: **{me['username']}**")
        st.write(f"Coins: **{me['coins']}**")
        if st.button("Logout"):
            st.session_state.auth = None
            st.session_state.room_code = ""
            st.rerun()

if not st.session_state.auth:
    st.info("Bitte zuerst registrieren oder einloggen.")
    st.stop()

user_id = int(st.session_state.auth["user_id"])

tabs = st.tabs(["Sammlung", "Deck", "Booster", "Räume", "Duell", "Katalog"])

# Sammlung
with tabs[0]:
    st.subheader("Ihre Sammlung")
    cards = get_collection(user_id)
    if not cards:
        st.caption("Noch keine Karten. Kaufen Sie Booster.")
    else:
        by_theme = {}
        for c in cards:
            by_theme.setdefault(c["theme"], []).append(c)
        for theme in ["feuer", "rd", "thl"]:
            if theme in by_theme:
                st.markdown(f"### {theme.upper()}")
                for c in sorted(by_theme[theme], key=lambda x: (x["rarity"], x["name"])):
                    st.write(f"{c['qty']}× {c['name']} ({c['code']}) – {c['rarity']}")

# Deck
with tabs[1]:
    st.subheader("Deck erstellen (exakt 40 Karten)")
    coll = get_collection(user_id)
    if not coll:
        st.info("Sie brauchen zuerst Karten (Booster), um ein Deck zu bauen.")
    else:
        deck = get_deck(user_id)
        current = deck.get("cards", {})
        st.caption("Deck muss exakt 40 Karten haben; pro Karte max. Besitzmenge.")
        new_cards = {}
        total = 0

        def sort_key(c):
            return (c["theme"], c["rarity"], c["name"])

        for c in sorted(coll, key=sort_key):
            code = c["code"]
            max_qty = int(c["qty"])
            default = int(current.get(code, 0))
            qty = st.number_input(
                f"{c['name']} ({code}) – Besitz: {max_qty} [{c['theme']}/{c['rarity']}]",
                min_value=0,
                max_value=max_qty,
                value=default,
                step=1,
                key=f"deck_{code}",
            )
            if qty > 0:
                new_cards[code] = int(qty)
                total += int(qty)

        st.info(f"Deckgröße: {total} / 40")
        if st.button("Deck speichern"):
            ok, msg = save_deck(user_id, "Standard", new_cards)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

# Booster
with tabs[2]:
    st.subheader("Booster kaufen & öffnen")
    col1, col2, col3 = st.columns(3)

    def buy(theme: str):
        ok, msg, payload = buy_open_booster(user_id, theme)
        if not ok:
            st.error(msg)
            return
        st.success(f"{msg} Coins jetzt: {payload['coins']}")
        for c in payload["cards"]:
            st.write(f"- {c['name']} ({c['code']}) – {c['rarity']}")

    with col1:
        st.markdown("### Feuer-Booster")
        st.caption("Mehr Feuerwehr-Fahrzeuge.")
        if st.button("Feuer-Booster kaufen (25 Coins)"):
            buy("feuer")
    with col2:
        st.markdown("### Rettungsdienst-Booster")
        st.caption("Mehr RD-Fahrzeuge.")
        if st.button("RD-Booster kaufen (25 Coins)"):
            buy("rd")
    with col3:
        st.markdown("### THL-Booster")
        st.caption("Mehr THL-Fahrzeuge.")
        if st.button("THL-Booster kaufen (25 Coins)"):
            buy("thl")

# Räume
with tabs[3]:
    st.subheader("Duellräume")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Raum erstellen")
        custom = st.text_input("Optionaler Raumcode", value="")
        if st.button("Erstellen"):
            ok, msg, code = create_room(user_id, custom or None)
            if ok:
                st.session_state.room_code = code
                st.success(f"{msg} Code: {code}")
            else:
                st.error(msg)

    with c2:
        st.markdown("### Raum beitreten")
        join_code = st.text_input("Raumcode", value=st.session_state.room_code)
        if st.button("Beitreten"):
            ok, msg = join_room(user_id, join_code)
            if ok:
                st.session_state.room_code = join_code.strip().upper()
                st.success(msg)
            else:
                st.error(msg)

    if st.session_state.room_code:
        st.divider()
        try:
            status = room_status(st.session_state.room_code)
            st.write(f"Aktueller Raum: **{status['room_code']}**")
            for p in status["players"]:
                st.write(f"- {p['username']} (id={p['id']})")
            if st.button("Match starten (2 Spieler + beide Decks)"):
                ok, msg = start_match(st.session_state.room_code)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        except Exception as e:
            st.error(str(e))

# Duell
with tabs[4]:
    st.subheader("Duell (Turn-based)")
    if not st.session_state.room_code:
        st.info("Bitte zuerst einen Raum erstellen/beitreten.")
    else:
        try:
            state = load_match(st.session_state.room_code)
        except Exception as e:
            st.error(f"Match nicht gestartet. {e}")
            st.stop()

        st.write(f"Runde: {state['round_no']} | Phase: **{state['phase']}** | Druck: {state['pressure']}/{state['pressure_max']}")
        st.write(f"Aktiver Spieler: **{state['active_player']}**")

        my = state["players"].get(str(user_id))
        if not my:
            st.error("Sie sind nicht Teil dieses Matches.")
            st.stop()

        st.write(f"Sie: EP={my['ep']} | Crew={my['crew']} | EW={my['ew']} | Draw-Pile={len(my.get('draw_pile', []))}")
        st.divider()

        cols = st.columns(2)
        for i in [0, 1]:
            with cols[i]:
                inc = state["open_incidents"][i]
                st.markdown(f"### Slot {i+1}: {inc['name']}")
                st.write(f"Zeit: {inc['time_left']} | EW: {inc['ew']}")
                st.write("Anforderungen:")
                st.json({k: v for k, v in inc["req"].items() if int(v) > 0})

        st.divider()
        st.markdown("## Ihre Hand")

        if not my["hand"]:
            st.caption("Keine Karten auf der Hand.")
        else:
            labels = []
            map_label = {}
            for code in my["hand"]:
                c = CATALOG.get(code)
                if c:
                    label = f"{c.name} ({c.code}) – EP {c.cost_ep} | Crew {c.crew} | {c.stats()}"
                else:
                    label = code
                labels.append(label)
                map_label[label] = code

            selected_label = st.selectbox("Karte wählen", labels)
            selected_code = map_label[selected_label]
            slot = st.radio("Slot", [0, 1], horizontal=True)

            if st.button("Zuweisen"):
                ok, msg = assign_card(st.session_state.room_code, user_id, slot, selected_code)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.divider()
        if st.button("Phase weiter"):
            ok, msg = advance_phase(st.session_state.room_code, user_id)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        with st.expander("Log (letzte 50)"):
            for line in state.get("log", [])[-50:]:
                st.write(line)

# Katalog
with tabs[5]:
    st.subheader("Katalog (alle Karten)")
    for theme in ["feuer", "rd", "thl"]:
        st.markdown(f"### {theme.upper()}")
        for c in sorted([x for x in CATALOG.values() if x.theme == theme], key=lambda x: (x.rarity, x.name)):
            st.write(f"{c.name} ({c.code}) – {c.rarity} | EP {c.cost_ep} | Crew {c.crew} | {c.stats()} | {c.text}")
