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

app = FastAPI(title="Berliner Feuerwehr TCG Backend", version="0.1.0")


# ==========================================================
# Data model (cards & incidents)
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
    theme: str = "feuer"      # feuer | rd | thl
    rarity: str = "C"        # C | U | R
    weight: int = 10         # higher => more common within theme
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


AXES = ["brand", "technik", "hoehe", "gefahrgut", "rettung", "koord"]


def vehicle_catalog() -> List[VehicleCard]:
    # Existing + your new vehicles + weighting + rarity + theme distribution
    # NOTE: Values are initial balancing placeholders; you can tune later.

    cards = [
        # ---- FEUER ----
        VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3, theme="feuer", rarity="U", weight=7, text="Allround."),
        VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1, theme="feuer", rarity="C", weight=14, text="Löschfahrzeug."),
        VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1, theme="feuer", rarity="U", weight=8, text="Höhenkomponente."),
        VehicleCard("V011", "TLF", 4, 1, brand=5, technik=1, theme="feuer", rarity="U", weight=7, text="Tanklöschfahrzeug."),
        VehicleCard("V012", "SW", 3, 1, brand=2, koord=1, theme="feuer", rarity="C", weight=10, text="Wasserversorgung/Logistik."),
        VehicleCard("V013", "ELW 2", 3, 1, koord=5, theme="feuer", rarity="R", weight=3, text="Führungs-/Koordination."),
        VehicleCard("V006", "GW-Gefahrgut", 4, 1, gefahrgut=5, theme="feuer", rarity="R", weight=3, text="Gefahrgut."),
        VehicleCard("V007", "TM 50", 4, 1, hoehe=5, theme="feuer", rarity="R", weight=3, text="Teleskopmast."),
        VehicleCard("V009", "Feuerwehrkran", 5, 1, technik=6, theme="feuer", rarity="R", weight=2, text="Schwerlast."),

        # ---- THL ----
        VehicleCard("V004", "RW", 4, 1, technik=5, theme="thl", rarity="U", weight=7, text="Rüstwagen."),
        VehicleCard("V005", "ELW 1", 2, 1, koord=3, theme="thl", rarity="C", weight=10, text="Einsatzleitung (leicht)."),
        VehicleCard("V019", "GW-Rüst", 3, 1, technik=3, theme="thl", rarity="C", weight=12, text="Gerätewagen THL."),
        VehicleCard("V020", "GW-L", 2, 1, technik=1, koord=1, theme="thl", rarity="C", weight=12, text="Logistik."),
        VehicleCard("V021", "VRW", 2, 1, technik=2, theme="thl", rarity="C", weight=10, text="Vorausrüstwagen."),
        VehicleCard("V022", "TLF-Wald", 4, 1, brand=5, theme="thl", rarity="U", weight=6, text="Waldbrandkomponente (optional)."),

        # ---- RETTUNGSDIENST (RD) ----
        VehicleCard("V014", "RTW", 2, 1, rettung=3, theme="rd", rarity="C", weight=18, text="Rettungstransportwagen."),
        VehicleCard("V015", "NEF", 2, 1, rettung=2, koord=1, theme="rd", rarity="C", weight=14, text="Notarzt."),
        VehicleCard("V016", "ITW", 4, 1, rettung=5, theme="rd", rarity="U", weight=6, text="Intensivtransport."),
        VehicleCard("V017", "RTH", 4, 1, rettung=4, hoehe=1, theme="rd", rarity="U", weight=6, text="Rettungshubschrauber."),
        VehicleCard("V018", "ITH", 5, 1, rettung=5, hoehe=1, theme="rd", rarity="R", weight=2, text="Intensivtransporthubschrauber."),
        VehicleCard("V023", "KTW", 1, 1, rettung=1, theme="rd", rarity="C", weight=18, text="Krankentransport."),
        VehicleCard("V024", "OrgL RD", 2, 1, koord=4, rettung=1, theme="rd", rarity="U", weight=5, text="Organisatorischer Leiter RD."),
    ]

    return cards


def incident_catalog() -> List[IncidentCard]:
    # Fire/THL + NEW: RD incidents using rettung/koord
    return [
        IncidentCard("I001", "Wohnungsbrand", ew=3, time_left=2,
                    req={"brand": 6}, tags=["feuer"], escalation_text="Anforderung +1 Brand, Druck +1"),
        IncidentCard("I002", "VU eingeklemmte Person", ew=3, time_left=2,
                    req={"technik": 5}, tags=["thl"], escalation_text="Druck +2"),
        IncidentCard("I003", "Hochhausbrand", ew=5, time_left=3,
                    req={"brand": 5, "hoehe": 4}, tags=["feuer"], escalation_text="Anforderungen +1, Druck +2"),
        IncidentCard("I004", "Gefahrgutunfall", ew=4, time_left=2,
                    req={"gefahrgut": 4}, tags=["feuer"], escalation_text="Druck +2"),
        IncidentCard("I005", "Bauunfall", ew=4, time_left=3,
                    req={"technik": 6}, tags=["thl"], escalation_text="Anforderung +1 Technik, Druck +1"),

        # ---- RD NEW ----
        IncidentCard("R001", "Reanimation", ew=3, time_left=2,
                    req={"rettung": 4}, tags=["rd"], escalation_text="Druck +2"),
        IncidentCard("R002", "Polytrauma", ew=4, time_left=2,
                    req={"rettung": 5}, tags=["rd"], escalation_text="Anforderung +1 Rettung, Druck +2"),
        IncidentCard("R003", "MANV (klein)", ew=5, time_left=3,
                    req={"rettung": 7, "koord": 3}, tags=["rd", "gross"], escalation_text="Druck +2, Anforderungen +1"),
        IncidentCard("R004", "Intensivtransport", ew=5, time_left=3,
                    req={"rettung": 6}, tags=["rd"], escalation_text="Druck +1"),
    ]


# ==========================================================
# SQLite helpers
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
        coins INTEGER NOT NULL DEFAULT 100
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
# Auth
# ==========================================================

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


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


# ==========================================================
# Booster logic
# ==========================================================

BOOSTER_COST = {
    "feuer": 25,
    "rd": 25,
    "thl": 25,
}

# rarity roll per slot (simple TCG-like):
# 4 common, 1 uncommon+, where + can upgrade to rare
def roll_rarity_for_slot(slot: int) -> str:
    if slot < 4:
        return "C"
    # last slot: 80% U, 20% R
    return "R" if random.random() < 0.20 else "U"


def pick_card(theme: str, rarity: str) -> VehicleCard:
    pool = [c for c in vehicle_catalog() if c.theme == theme and c.rarity == rarity]
    if not pool:
        # fallback: any in theme
        pool = [c for c in vehicle_catalog() if c.theme == theme]
    weights = [max(1, c.weight) for c in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def open_booster(theme: str) -> List[VehicleCard]:
    cards: List[VehicleCard] = []
    for i in range(5):
        rarity = roll_rarity_for_slot(i)
        cards.append(pick_card(theme, rarity))
    return cards


def add_cards_to_user(con: sqlite3.Connection, user_id: int, card_codes: List[str]) -> None:
    for code in card_codes:
        cur = con.execute("SELECT qty FROM user_cards WHERE user_id=? AND card_code=?", (user_id, code)).fetchone()
        if cur:
            con.execute("UPDATE user_cards SET qty=qty+1 WHERE user_id=? AND card_code=?", (user_id, code))
        else:
            con.execute("INSERT INTO user_cards(user_id, card_code, qty) VALUES (?, ?, 1)", (user_id, code))
    con.commit()


# ==========================================================
# Match state (turn-based, stored JSON)
# ==========================================================

def new_match_state(p1_id: int, p2_id: int) -> dict:
    incidents = incident_catalog()
    inc1 = random.choice(incidents)
    inc2 = random.choice(incidents)

    # Start hands: 10 vehicles drawn as codes (duplicates allowed)
    # For MVP we draw from theme-mix pool; later we use user's actual collection/deckbuilding.
    all_cards = vehicle_catalog()
    hand1 = [random.choice(all_cards).code for _ in range(10)]
    hand2 = [random.choice(all_cards).code for _ in range(10)]

    return {
        "version": "mvp0.1",
        "round_no": 1,
        "phase": "planung",
        "pressure": 0,
        "pressure_max": 12,
        "active_player": p1_id,
        "players": {
            str(p1_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand1},
            str(p2_id): {"ep": 6, "crew": 5, "ew": 0, "hand": hand2},
        },
        "open_incidents": [asdict(inc1), asdict(inc2)],
        "assignments": {"0": [], "1": []},  # list of {"user_id":..., "card_code":...}
        "assigned_this_turn": {str(p1_id): False, str(p2_id): False},
        "round_ew_snapshot": {str(p1_id): 0, str(p2_id): 0},
        "log": [],
    }


def card_by_code(code: str) -> VehicleCard:
    for c in vehicle_catalog():
        if c.code == code:
            return c
    raise KeyError(code)


def requirements_met(req: Dict[str, int], total: Dict[str, int]) -> bool:
    for k, v in req.items():
        if total.get(k, 0) < v:
            return False
    return True


def apply_resources(state: dict, user_id: int) -> None:
    # v1.1 resources
    p = state["players"][str(user_id)]
    pressure = state["pressure"]
    p["ep"] = min(10, p["ep"] + 2)
    regen = 1
    if pressure >= 8:
        regen = max(0, regen - 1)
    p["crew"] = min(7, p["crew"] + regen)


def end_of_full_round_bonus(state: dict) -> Optional[int]:
    # determine who gained more EW since snapshot; winner draws 5
    gains = {}
    for uid_str, pdata in state["players"].items():
        prev = state["round_ew_snapshot"].get(uid_str, 0)
        gains[uid_str] = pdata["ew"] - prev
    max_gain = max(gains.values()) if gains else 0
    winners = [uid for uid, g in gains.items() if g == max_gain and g > 0]
    if len(winners) == 1:
        return int(winners[0])
    return None


def draw_vehicles_to_hand(state: dict, user_id: int, n: int) -> List[str]:
    all_cards = vehicle_catalog()
    drawn = [random.choice(all_cards).code for _ in range(n)]
    state["players"][str(user_id)]["hand"].extend(drawn)
    return drawn


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


# ==========================================================
# API Endpoints
# ==========================================================

@app.post("/auth/register")
def register(req: RegisterReq):
    con = db()
    try:
        con.execute("INSERT INTO users(username, password, coins) VALUES (?, ?, ?)", (req.username, req.password, 100))
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        con.close()
    return {"ok": True}


@app.post("/auth/login")
def login(req: LoginReq):
    con = db()
    user = con.execute("SELECT * FROM users WHERE username=? AND password=?", (req.username, req.password)).fetchone()
    if not user:
        con.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(con, user["id"])
    con.close()
    return {"token": token, "user_id": user["id"], "coins": user["coins"]}


def require_user(x_token: Optional[str]) -> Tuple[sqlite3.Connection, sqlite3.Row]:
    if not x_token:
        raise HTTPException(status_code=401, detail="Missing X-Token header")
    con = db()
    user = get_user_from_token(con, x_token)
    return con, user


@app.get("/me")
def me(x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    con.close()
    return {"user_id": user["id"], "username": user["username"], "coins": user["coins"]}


@app.get("/collection")
def collection(x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    rows = con.execute("SELECT card_code, qty FROM user_cards WHERE user_id=? ORDER BY card_code", (user["id"],)).fetchall()
    con.close()

    # enrich with card metadata
    catalog = {c.code: c for c in vehicle_catalog()}
    result = []
    for r in rows:
        c = catalog.get(r["card_code"])
        if c:
            result.append({"code": c.code, "name": c.name, "qty": r["qty"], "theme": c.theme, "rarity": c.rarity})
    return {"cards": result}


@app.post("/booster/buy_open")
def buy_open(req: BuyBoosterReq, x_token: Optional[str] = Header(default=None)):
    theme = req.theme.lower().strip()
    if theme not in BOOSTER_COST:
        raise HTTPException(status_code=400, detail="Invalid theme")

    con, user = require_user(x_token)
    cost = BOOSTER_COST[theme]

    if user["coins"] < cost:
        con.close()
        raise HTTPException(status_code=400, detail="Not enough coins")

    cards = open_booster(theme)
    codes = [c.code for c in cards]

    con.execute("UPDATE users SET coins=coins-? WHERE id=?", (cost, user["id"]))
    add_cards_to_user(con, user["id"], codes)

    # refresh coins
    new_user = con.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    con.close()

    return {
        "theme": theme,
        "cost": cost,
        "coins": new_user["coins"],
        "cards": [{"code": c.code, "name": c.name, "rarity": c.rarity, "theme": c.theme} for c in cards],
    }


@app.post("/room/create")
def room_create(req: CreateRoomReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = (req.room_code or "").strip().upper()
    if not code:
        code = secrets.token_hex(3).upper()

    exists = con.execute("SELECT room_code FROM rooms WHERE room_code=?", (code,)).fetchone()
    if exists:
        con.close()
        raise HTTPException(status_code=400, detail="Room code already exists")

    now = int(time.time())
    con.execute("INSERT INTO rooms(room_code, host_user_id, created_at) VALUES (?, ?, ?)", (code, user["id"], now))
    con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, user["id"], now))
    con.commit()
    con.close()
    return {"room_code": code}


@app.post("/room/join")
def room_join(req: JoinRoomReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = req.room_code.strip().upper()
    room = con.execute("SELECT * FROM rooms WHERE room_code=?", (code,)).fetchone()
    if not room:
        con.close()
        raise HTTPException(status_code=404, detail="Room not found")

    now = int(time.time())
    try:
        con.execute("INSERT INTO room_players(room_code, user_id, joined_at) VALUES (?, ?, ?)", (code, user["id"], now))
        con.commit()
    except sqlite3.IntegrityError:
        pass  # already joined
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
    return {"room_code": code, "players": [{"id": p["id"], "username": p["username"]} for p in players], "match_started": bool(match)}


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
        raise HTTPException(status_code=400, detail="MVP requires exactly 2 players in room")

    exists = con.execute("SELECT room_code FROM matches WHERE room_code=?", (code,)).fetchone()
    if exists:
        con.close()
        return {"ok": True, "room_code": code}

    p1_id = int(players[0]["id"])
    p2_id = int(players[1]["id"])
    state = new_match_state(p1_id, p2_id)

    con.execute("INSERT INTO matches(room_code, state_json, updated_at) VALUES (?, ?, ?)", (code, json.dumps(state), int(time.time())))
    con.commit()
    con.close()
    return {"ok": True, "room_code": code}


def load_match(con: sqlite3.Connection, room_code: str) -> dict:
    row = con.execute("SELECT state_json FROM matches WHERE room_code=?", (room_code,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return json.loads(row["state_json"])


def save_match(con: sqlite3.Connection, room_code: str, state: dict) -> None:
    con.execute("UPDATE matches SET state_json=?, updated_at=? WHERE room_code=?", (json.dumps(state), int(time.time()), room_code))
    con.commit()


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
    code = req.room_code.strip().upper()
    state = load_match(con, code)

    if state["phase"] != "planung":
        con.close()
        raise HTTPException(status_code=400, detail="Assign only allowed in planung phase")

    if state["active_player"] != user["id"]:
        con.close()
        raise HTTPException(status_code=400, detail="Not your turn")

    slot = int(req.slot)
    if slot not in [0, 1]:
        con.close()
        raise HTTPException(status_code=400, detail="Invalid slot")

    uid = str(user["id"])
    if state["assigned_this_turn"].get(uid, False):
        con.close()
        raise HTTPException(status_code=400, detail="Already assigned this turn (MVP rule)")

    hand = state["players"][uid]["hand"]
    if req.card_code not in hand:
        con.close()
        raise HTTPException(status_code=400, detail="Card not in hand")

    card = card_by_code(req.card_code)

    cost = card.cost_ep + (1 if state["pressure"] >= 5 else 0)
    if state["players"][uid]["ep"] < cost:
        con.close()
        raise HTTPException(status_code=400, detail=f"Not enough EP (need {cost})")
    if state["players"][uid]["crew"] < card.crew:
        con.close()
        raise HTTPException(status_code=400, detail="Not enough crew")

    state["players"][uid]["ep"] -= cost
    state["players"][uid]["crew"] -= card.crew
    hand.remove(req.card_code)

    state["assignments"][str(slot)].append({"user_id": user["id"], "card_code": req.card_code})
    state["assigned_this_turn"][uid] = True
    state["log"].append(f"{user['username']} weist {card.name} zu Slot {slot+1} zu (Kosten {cost} EP).")

    save_match(con, code, state)
    con.close()
    return {"ok": True}


def resolve_phase(state: dict) -> None:
    incidents = state["open_incidents"]
    for slot_idx in [0, 1]:
        inc = incidents[slot_idx]
        req = inc["req"]

        assigned = state["assignments"][str(slot_idx)]
        totals = {k: 0 for k in AXES}
        contrib = {}

        for a in assigned:
            c = card_by_code(a["card_code"])
            pw = c.__dict__
            for k in AXES:
                totals[k] += int(pw.get(k, 0))
            uid = str(a["user_id"])
            contrib[uid] = contrib.get(uid, 0) + sum(int(pw.get(k, 0)) for k in AXES)

        ok = requirements_met(req, totals)
        state["log"].append(f"Resolve Slot {slot_idx+1} '{inc['name']}': req={req} totals={totals}")

        if ok:
            if contrib:
                winner_uid = max(contrib.items(), key=lambda x: x[1])[0]
                extra = 1 if state.get("global_media_bonus_next_resolve", False) else 0
                state["players"][winner_uid]["ew"] += inc["ew"] + extra
                state["log"].append(f"Erfüllt. Sieger {winner_uid} erhält {inc['ew']}+{extra} EW.")
            # replace incident
            new_inc = asdict(random.choice(incident_catalog()))
            state["open_incidents"][slot_idx] = new_inc
        else:
            state["log"].append("Nicht erfüllt. Eskalation folgt.")

        state["assignments"][str(slot_idx)] = []


def escalate_phase(state: dict) -> None:
    for slot_idx in [0, 1]:
        inc = state["open_incidents"][slot_idx]
        inc["time_left"] -= 1
        state["pressure"] += 1

        if inc["time_left"] <= 0:
            # add +1 to each nonzero requirement
            for k, v in list(inc["req"].items()):
                if v > 0:
                    inc["req"][k] = v + 1
            # extra pressure on special tags
            extra = 2 if any(t in inc["tags"] for t in ["gross"]) else 1
            state["pressure"] += extra
            inc["time_left"] = 2
            state["log"].append(f"Eskalation in Slot {slot_idx+1}: req+1, Druck +{extra}, reset time=2.")


@app.post("/match/advance_phase")
def match_advance_phase(req: AdvancePhaseReq, x_token: Optional[str] = Header(default=None)):
    con, user = require_user(x_token)
    code = req.room_code.strip().upper()
    state = load_match(con, code)

    if state["active_player"] != user["id"]:
        con.close()
        raise HTTPException(status_code=400, detail="Not your turn")

    phase = state["phase"]

    if phase == "planung":
        state["phase"] = "einsatz"
        state["log"].append("Phase -> Einsatz.")
    elif phase == "einsatz":
        # resolve
        resolve_phase(state)
        state["phase"] = "eskalation"
        state["log"].append("Phase -> Eskalation.")
    elif phase == "eskalation":
        # escalate, then turn switch
        escalate_phase(state)

        # switch active player
        player_ids = list(map(int, state["players"].keys()))
        player_ids.sort()
        other = player_ids[0] if user["id"] == player_ids[1] else player_ids[1]
        state["active_player"] = other

        # reset per-turn assignment
        for uid in state["assigned_this_turn"].keys():
            state["assigned_this_turn"][uid] = False

        # resources for next player
        apply_resources(state, other)

        # full round check: when it becomes player1 again (small convention: lower id is p1)
        if other == player_ids[0]:
            winner = end_of_full_round_bonus(state)
            if winner is not None:
                drawn = draw_vehicles_to_hand(state, winner, 5)
                state["log"].append(f"Runden-Sieger {winner} zieht 5 Karten: {drawn}")
            # snapshot refresh
            for uid in state["players"].keys():
                state["round_ew_snapshot"][uid] = state["players"][uid]["ew"]
            state["round_no"] += 1

        state["phase"] = "planung"
        state["log"].append("Zugwechsel. Phase -> Planung.")
    else:
        con.close()
        raise HTTPException(status_code=400, detail="Invalid phase")

    save_match(con, code, state)
    con.close()
    return {"ok": True}

