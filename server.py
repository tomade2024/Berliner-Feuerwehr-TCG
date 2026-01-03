from __future__ import annotations

import json
import os
import random
import secrets
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

DB_PATH = os.environ.get("BFTCG_DB", "bftcg.sqlite3")

app = FastAPI(title="Berliner Feuerwehr TCG Backend", version="0.2.0")

AXES = ["brand", "technik", "hoehe", "gefahrgut", "rettung", "koord"]

START_COINS = 250  # damit Deckbuilding sofort erreichbar ist
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 Tage

BOOSTER_COST = {"feuer": 25, "rd": 25, "thl": 25}


# ==========================================================
# Catalog (Vehicles & Incidents)
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
    theme: str = "feuer"    # feuer | rd | thl
    rarity: str = "C"      # C | U | R
    weight: int = 10       # more => more common within theme+rarity pool
    text: str = ""


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
    # Values are initial placeholders; tune later.
    return [
        # ---- FEUER ----
        VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1, theme="feuer", rarity="C", weight=18, text="Löschfahrzeug."),
        VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3, theme="feuer", rarity="U", weight=10, text="Allround."),
        VehicleCard("V011", "TLF", 4, 1, brand=5, technik=1, theme="feuer", rarity="U", weight=9, text="Tanklöschfahrzeug."),
        VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1, theme="feuer", rarity="U", weight=10, text="Höhenkomponente."),
        VehicleCard("V012", "SW", 3, 1, brand=2, koord=1, theme="feuer", rarity="C", weight=14, text="Wasserversorgung/Logistik."),
        VehicleCard("V006", "GW-Gefahrgut", 4, 1, gefahrgut=5, theme="feuer", rarity="R", weight=4, text="Gefahrgut-Spezialist."),
        VehicleCard("V007", "TM 50", 4, 1, hoehe=5, theme="feuer", rarity="R", weight=4, text="Teleskopmast."),
        VehicleCard("V009", "Feuerwehrkran", 5, 1, technik=6, theme="feuer", rarity="R", weight=3, text="Schwerlast."),
        VehicleCard("V013", "ELW 2", 3, 1, koord=5, theme="feuer", rarity="R", weight=3, text="Führung/Koordination."),

        # ---- THL ----
        VehicleCard("V004", "RW", 4, 1, technik=5, theme="thl", rarity="U", weight=10, text="Rüstwagen."),
        VehicleCard("V005", "ELW 1", 2, 1, koord=3, theme="thl", rarity="C", weight=14, text="Einsatzleitung (leicht)."),
        VehicleCard("V019", "GW-Rüst", 3, 1, technik=3, theme="thl", rarity="C", weight=16, text="Gerätewagen THL."),
        VehicleCard("V020", "GW-L", 2, 1, technik=1, koord=1, theme="thl", rarity="C", weight=16, text="Logistik."),
        VehicleCard("V021", "VRW", 2, 1, technik=2, theme="thl", rarity="C", weight=14, text="Vorausrüstwagen."),

        # ---- RETTUNGSDIENST ----
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

        # RETTUNGSDIENST (NEU)
        IncidentCard("R001", "Reanimation", ew=3, time_left=2, req={"rettung": 4}, tags=["rd"], escalation_text="Druck +2"),
        IncidentCard("R002", "Polytrauma", ew=4, time_left=2, req={"rettung": 5}, tags=["rd"], escalation_text="Anforderung +1 Rettung, Druck +2"),
        IncidentCard("R003", "MANV (klein)", ew=5, time_left=3, req={"rettung": 7, "koord": 3}, tags=["rd", "gross"], escalation_text="Druck +2, Anforderungen +1"),
        IncidentCard("R004", "Intensivtransport", ew=5, time_left=3, req={"rettung": 6}, tags=["rd"], escalation_text="Druck +1"),
    ]


def card_by_code(code: str) -> VehicleCard:
    for c in vehicle_catalog():
        if c.code == code:
            return c
    raise HTTPException(status_code=400, detail=f"Unknown card code: {code}")


# ==========================================================
# DB
# ==========================================================

def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
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
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
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

    # Deckbuilding
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

    # Rooms / matches
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


@app.on_event("startup")
def _startup():
    init_db()


# ==========================================================
# Auth helpers
# ==========================================================

def create_token(con: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    exp = int(time.time()) + TOKEN_TTL_SECONDS
    con.execute("INSERT INTO tokens(token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, exp))
    con.commit()
    return token


def get_user_from_token(con: sqlite3.Connection, token: str) -> sqlite3.Row:
    row = con.execute("SELECT user_id, expires_at FROM tokens WHERE token=?", (token,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid token")
    if int(row["expires_at"]) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")
    user = con.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_user(x_token: Optional[str]) -> Tuple[sqlite3.Connection, sqlite3.Row]:
    if not x_token:
        raise HTTPException(status_code=401, detail="Missing X-Token header")
    con = db()
    user = get_user_from_token(con, x_token)
    return con, user


# ==========================================================
# Booster logic (weighted)
# ==========================================================

def roll_rarity_for_slot(slot: int) -> str:
    # 4x Common, last slot: 80% Uncommon, 20% Rare
    if slot < 4:
        return "C"
    return "R" if random.random() < 0.20 else "U"


def pick_card(theme: str, rarity: str) -> VehicleCard:
    pool = [c for c in vehicle_catalog() if c.theme == theme and c.rarity == rarity]
    if not pool:
        pool = [c for c in vehicle_catalog() if c.theme == theme]
    weights = [max(1, int(c.weight)) for c in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def open_booster(theme: str) -> List[VehicleCard]:
    return [pick_card(theme, roll_rarity_for_slot(i)) for i in range(5)]


def add_cards_to_user(con: sqlite3.Connection, user_id: int, card_codes: List[str]) -> None:
    for code in card_codes:
        row = con.execute(
            "SELECT qty FROM user_cards WHERE user_id=? AND card_code=?",
            (user_id, code),
        ).fetchone()
        if row:
            con.execute(
                "UPDATE user_cards SET qty=qty+1 WHERE user_id=? AND card_code=?",
                (user_id, code),
            )
        else:
            con.execute(
                "INSERT INTO user_cards(user_id, card_code, qty) VALUES (?, ?, 1)",
                (user_id, code),
            )
    con.commit()


# ==========================================================
# Deck helpers
# ==========================================================

def get_deck_list(con: sqlite3.Connection, user_id: int) -> List[str]:
    rows = con.execute("SELECT card_code, qty FROM deck_cards WHERE user_id=?", (user_id,)).fetchall()
    cards: List[str] = []
    for r in rows:
        cards.extend([r["card_code"]] * int(r["qty"]))
    if len(cards) != 40:
        raise HTTPException(status_code=400, detail=f"User {user_id} hat kein gültiges 40er-Deck.")
    return cards


# ==========================================================
# Match state
# ==========================================================

def requirements_met(req: Dict[str, int], total: Dict[str, int]) -> bool:
    for k, v in req.items():
        if total.get(k, 0) < v:
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


def draw_from_pile(state: dict, user_id: int, n: int) -> List[str]:
    uid = str(user_id)
    pile = state["players"][uid]["draw_pile"]
    hand = state["players"][uid]["hand"]
    drawn: List[str] = []
    for _ in range(n):
        if not pile:
            break
        drawn.append(pile.pop())
    hand.extend(drawn)
    return drawn


def new_match_state(p1_id: int, p2_id: int, deck1: List[str], deck2: List[str]) -> dict:
    incs = incident_catalog()
    inc1 = asdict(random.choice(incs))
    inc2 = asdict(random.choice(incs))

    draw_pile_1 = deck1[:]
    draw_pile_2 = deck2[:]
    hand1 = []
    hand2 = []
    for _ in range(10):
        hand1.append(draw_pile_1.pop())
        hand2.append(draw_pile_2.pop())

    return {
        "version": "mvp0.2",
        "round_no": 1,
        "phase": "planung",
        "pressure": 0,
        "pressure_max": 12,
        "active_player": p1_id,
        "players": {
            str(p1_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand1, "draw_pile": draw_pile_1},
            str(p2_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand2, "draw_pile": draw_pile_2},
        },
        "open_incidents": [inc1, inc2],
        "assignments": {"0": [], "1": []},  # list of {"user_id":..., "card_code":...}
        "assigned_this_turn": {str(p1_id): False, str(p2_id): False},
        "round_ew_snapshot": {str(p1_id): 0, str(p2_id): 0},
        "log": [],
    }


def load_match(con: sqlite3.Connection, room_code: str) -> dict:
    row = con.execute("SELECT state_json FROM matches WHERE room_code=?", (room_code,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return json.loads(row["state_json"])


def save_match(con: sqlite3.Connection, room_code: str, state: dict) -> None:
    con.execute(
        "UPDATE matches SET state_json=?, updated_at=? WHERE room_code=?",
        (json.dumps(state), int(time.time()), room_code),
    )
    con.commit()


def resolve_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        req = inc["req"]

        assigned = state["assignments"][str(slot_idx)]
        totals = {k: 0 for k in AXES}
        contrib = {}

        for a in assigned:
            c = card_by_code(a["card_code"])
            for k in AXES:
                totals[k] += int(getattr(c, k))
            uid = str(a["user_id"])
            contrib[uid] = contrib.get(uid, 0) + sum(int(getattr(c, k)) for k in AXES)

        ok = requirements_met(req, totals)
        state["log"].append(f"Resolve Slot {slot_idx+1} '{inc['name']}': req={req} totals={totals}")

        if ok:
            if contrib:
                winner_uid = max(contrib.items(), key=lambda x: x[1])[0]
                extra = 1 if state.get("global_media_bonus_next_resolve", False) else 0
                state["players"][winner_uid]["ew"] += int(inc["ew"]) + extra
                state["log"].append(f"Erfüllt. Sieger {winner_uid} erhält {inc['ew']}+{extra} EW.")
            # replace incident
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


# ==========================================================
# API Schemas
# ==========================================================

class RegisterReq(BaseModel):
    username: str
    password: str


class LoginReq(BaseModel):
    username: str
    password: str


class BuyBoosterReq(BaseModel):
    theme: str  # feuer|rd|thl


class CreateRoomReq(BaseModel):
    room_code: Optional[str] = None


class JoinRoomReq(BaseModel):
    room_code: str


class StartMatchReq(BaseModel):
    room_code: str


class AssignReq(BaseModel):
    room_code: str
    slot: int
    card_code: str


class AdvancePhaseReq(BaseModel):
    room_code: str


class DeckSaveReq(BaseModel):
    name: str = "Standard"
    cards: Dict[str, int]  # code -> qty (must total 40)


# ==========================================================
# Catalog endpoints
# ==========================================================

@app.get("/catalog/vehicles")
def catalog_vehicles():
    cards = vehicle_catalog()
    return {
        "cards": [
            {
                "code": c.code,
                "name": c.name,
                "theme": c.theme,
                "rarity": c.rarity,
                "cost_ep": c.cost_ep,
                "crew": c.crew,
                "stats": {k: int(getattr(c, k)) for k in AXES},
                "text": c.text,
            }
            for c in cards
        ]
    }


@app.get("/catalog/incidents")
def catalog_incidents():
    incs = incident_catalog()
    return {"incidents": [asdict(i) for i in incs]}


# ==========================================================
# Auth endpoints
# ==========================================================

@app.post("/auth/register")
def register(req: RegisterReq):
    con = db()
    try:
        con.execute(
            "INSERT INTO users(username, password, coins) VALUES (?, ?, ?)",
            (req.username, req.password, START_COINS),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    con.close()
    return {"ok": True, "start_coins": START_COINS}


@app.post("/auth/login")
def login(req: LoginReq):
    con = db()
    user = con.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (req.username, req.password),
    ).fetchone()
    if not user:
        con.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(con, int(user["id"]))
    coins = int(user["coins"])
    con.close()
    return {"token": token, "user_id": int(user["id"]), "coins": coins}


@app.get("/me")
def me(x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    res = {"user_id": int(user["id"]), "username": user["username"], "coins": int(user["coins"])}
    con.close()
    return res


# ==========================================================
# Collection + deck endpoints
# ==========================================================

@app.get("/collection")
def collection(x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    rows = con.execute(
        "SELECT card_code, qty FROM user_cards WHERE user_id=? ORDER BY card_code",
        (int(user["id"]),),
    ).fetchall()
    con.close()

    catalog = {c.code: c for c in vehicle_catalog()}
    result = []
    for r in rows:
        c = catalog.get(r["card_code"])
        if c:
            result.append({"code": c.code, "name": c.name, "qty": int(r["qty"]), "theme": c.theme, "rarity": c.rarity})
    return {"cards": result}


@app.get("/deck/get")
def deck_get(x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    deck = con.execute("SELECT name, size FROM decks WHERE user_id=?", (int(user["id"]),)).fetchone()
    rows = con.execute("SELECT card_code, qty FROM deck_cards WHERE user_id=?", (int(user["id"]),)).fetchall()
    con.close()
    return {
        "name": deck["name"] if deck else "Standard",
        "size": int(deck["size"]) if deck else 40,
        "cards": {r["card_code"]: int(r["qty"]) for r in rows},
    }


@app.post("/deck/save")
def deck_save(req: DeckSaveReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    uid = int(user["id"])

    total = sum(int(v) for v in req.cards.values() if int(v) > 0)
    if total != 40:
        con.close()
        raise HTTPException(status_code=400, detail=f"Deck muss exakt 40 Karten haben (aktuell {total}).")

    owned_rows = con.execute("SELECT card_code, qty FROM user_cards WHERE user_id=?", (uid,)).fetchall()
    owned = {r["card_code"]: int(r["qty"]) for r in owned_rows}

    for code, qty in req.cards.items():
        q = int(qty)
        if q < 0:
            con.close()
            raise HTTPException(status_code=400, detail="Negative Mengen sind nicht erlaubt.")
        if q > 0 and owned.get(code, 0) < q:
            con.close()
            raise HTTPException(status_code=400, detail=f"Nicht genug Kopien für {code}: benötigt {q}, vorhanden {owned.get(code, 0)}")

    con.execute("INSERT OR REPLACE INTO decks(user_id, name, size) VALUES (?, ?, ?)", (uid, req.name, 40))
    con.execute("DELETE FROM deck_cards WHERE user_id=?", (uid,))
    for code, qty in req.cards.items():
        q = int(qty)
        if q > 0:
            con.execute("INSERT INTO deck_cards(user_id, card_code, qty) VALUES (?, ?, ?)", (uid, code, q))
    con.commit()
    con.close()
    return {"ok": True}


# ==========================================================
# Booster endpoints
# ==========================================================

@app.post("/booster/buy_open")
def buy_open(req: BuyBoosterReq, x_token: Optional[str] = Header(default=None)):
    theme = req.theme.lower().strip()
    if theme not in BOOSTER_COST:
        raise HTTPException(status_code=400, detail="Invalid theme")

    con, user = require_user(x_token)
    uid = int(user["id"])

    cost = int(BOOSTER_COST[theme])
    coins = int(user["coins"])
    if coins < cost:
        con.close()
        raise HTTPException(status_code=400, detail="Not enough coins")

    cards = open_booster(theme)
    codes = [c.code for c in cards]

    con.execute("UPDATE users SET coins=coins-? WHERE id=?", (cost, uid))
    add_cards_to_user(con, uid, codes)

    new_user = con.execute("SELECT coins FROM users WHERE id=?", (uid,)).fetchone()
    con.close()

    return {
        "theme": theme,
        "cost": cost,
        "coins": int(new_user["coins"]),
        "cards": [{"code": c.code, "name": c.name, "rarity": c.rarity, "theme": c.theme} for c in cards],
    }


# ==========================================================
# Rooms / matches
# ==========================================================

@app.post("/room/create")
def room_create(req: CreateRoomReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    uid = int(user["id"])

    code = (req.room_code or "").strip().upper()
    if not code:
        code = secrets.token_hex(3).upper()

    exists = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (code,)).fetchone()
    if exists:
        con.close()
        raise HTTPException(status_code=400, detail="Room code already exists")

    now = int(time.time())
    con.execute("INSERT INTO rooms(room_code, host_user_id, created_at) VALUES (?, ?, ?)", (code, uid, now))
    con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, uid, now))
    con.commit()
    con.close()
    return {"room_code": code}


@app.post("/room/join")
def room_join(req: JoinRoomReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    uid = int(user["id"])
    code = req.room_code.strip().upper()

    room = con.execute("SELECT * FROM rooms WHERE room_code=?", (code,)).fetchone()
    if not room:
        con.close()
        raise HTTPException(status_code=404, detail="Room not found")

    now = int(time.time())
    try:
        con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, uid, now))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()
    return {"room_code": code}


@app.get("/room/status")
def room_status(room_code: str, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = room_code.strip().upper()

    room = con.execute("SELECT * FROM rooms WHERE room_code=?", (code,)).fetchone()
    if not room:
        con.close()
        raise HTTPException(status_code=404, detail="Room not found")

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


@app.post("/match/start")
def match_start(req: StartMatchReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = req.room_code.strip().upper()

    players = con.execute("""
        SELECT u.id FROM room_players rp
        JOIN users u ON u.id = rp.user_id
        WHERE rp.room_code=?
        ORDER BY rp.joined_at
    """, (code,)).fetchall()

    if len(players) != 2:
        con.close()
        raise HTTPException(status_code=400, detail="MVP: Genau 2 Spieler im Raum erforderlich.")

    exists = con.execute("SELECT room_code FROM matches WHERE room_code=?", (code,)).fetchone()
    if exists:
        con.close()
        return {"ok": True, "room_code": code}

    p1_id = int(players[0]["id"])
    p2_id = int(players[1]["id"])

    # Decks laden
    deck1 = get_deck_list(con, p1_id)
    deck2 = get_deck_list(con, p2_id)
    random.shuffle(deck1)
    random.shuffle(deck2)

    state = new_match_state(p1_id, p2_id, deck1, deck2)

    con.execute(
        "INSERT INTO matches(room_code, state_json, updated_at) VALUES (?, ?, ?)",
        (code, json.dumps(state), int(time.time())),
    )
    con.commit()
    con.close()
    return {"ok": True, "room_code": code}


@app.get("/match/state")
def match_state(room_code: str, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = room_code.strip().upper()
    state = load_match(con, code)
    con.close()
    return state


@app.post("/match/assign")
def match_assign(req: AssignReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    uid = int(user["id"])
    uname = user["username"]
    code = req.room_code.strip().upper()
    state = load_match(con, code)

    if state["phase"] != "planung":
        con.close()
        raise HTTPException(status_code=400, detail="Assign nur in Planungsphase möglich.")
    if int(state["active_player"]) != uid:
        con.close()
        raise HTTPException(status_code=400, detail="Nicht dein Zug.")

    slot = int(req.slot)
    if slot not in [0, 1]:
        con.close()
        raise HTTPException(status_code=400, detail="Invalid slot.")

    uid_str = str(uid)
    if state["assigned_this_turn"].get(uid_str, False):
        con.close()
        raise HTTPException(status_code=400, detail="Bereits diese Runde zugewiesen (MVP-Regel).")

    hand = state["players"][uid_str]["hand"]
    if req.card_code not in hand:
        con.close()
        raise HTTPException(status_code=400, detail="Karte nicht auf der Hand.")

    card = card_by_code(req.card_code)

    pressure = int(state["pressure"])
    cost = int(card.cost_ep) + (1 if pressure >= 5 else 0)

    if int(state["players"][uid_str]["ep"]) < cost:
        con.close()
        raise HTTPException(status_code=400, detail=f"Nicht genug EP (benötigt {cost}).")
    if int(state["players"][uid_str]["crew"]) < int(card.crew):
        con.close()
        raise HTTPException(status_code=400, detail="Nicht genug Personal.")

    state["players"][uid_str]["ep"] -= cost
    state["players"][uid_str]["crew"] -= int(card.crew)
    hand.remove(req.card_code)

    state["assignments"][str(slot)].append({"user_id": uid, "card_code": req.card_code})
    state["assigned_this_turn"][uid_str] = True
    state["log"].append(f"{uname} weist {card.name} Slot {slot+1} zu (Kosten {cost} EP).")

    save_match(con, code, state)
    con.close()
    return {"ok": True}


@app.post("/match/advance_phase")
def match_advance_phase(req: AdvancePhaseReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    uid = int(user["id"])
    code = req.room_code.strip().upper()
    state = load_match(con, code)

    if int(state["active_player"]) != uid:
        con.close()
        raise HTTPException(status_code=400, detail="Nicht dein Zug.")

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

        # switch active player (two-player MVP)
        pids = list(map(int, state["players"].keys()))
        pids.sort()
        other = pids[0] if uid == pids[1] else pids[1]
        state["active_player"] = other

        # reset per-turn assignment
        for k in list(state["assigned_this_turn"].keys()):
            state["assigned_this_turn"][k] = False

        # resources for next player
        apply_resources(state, other)

        # full round check when lower id becomes active again
        if other == pids[0]:
            winner = end_of_full_round_winner(state)
            if winner is not None:
                # +5 coins persistent
                con.execute("UPDATE users SET coins=coins+5 WHERE id=?", (winner,))
                state["log"].append(f"Runden-Sieger {winner} erhält +5 Coins.")

                # match reward: draw 5 from own draw pile
                drawn = draw_from_pile(state, winner, 5)
                state["log"].append(f"Runden-Sieger {winner} zieht 5 Karten aus Deck: {drawn}")

            # snapshot refresh + round increment
            for uid_str in list(state["players"].keys()):
                state["round_ew_snapshot"][uid_str] = int(state["players"][uid_str]["ew"])
            state["round_no"] += 1

        state["phase"] = "planung"
        state["log"].append("Zugwechsel. Phase -> Planung.")
    else:
        con.close()
        raise HTTPException(status_code=400, detail="Invalid phase.")

    save_match(con, code, state)
    con.close()
    return {"ok": True}
