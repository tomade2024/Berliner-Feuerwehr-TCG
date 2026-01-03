import streamlit as st
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Dict, List

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Berliner Feuerwehr TCG", layout="wide")
AXES = ["brand", "technik", "hoehe", "rettung", "koord"]
DB_PATH = "bftcg.sqlite3"
START_COINS = 250

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
        username TEXT UNIQUE,
        coins INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_cards(
        user_id INTEGER,
        card_code TEXT,
        qty INTEGER,
        PRIMARY KEY(user_id, card_code)
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS decks(
        user_id INTEGER PRIMARY KEY,
        name TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deck_cards(
        user_id INTEGER,
        card_code TEXT,
        qty INTEGER,
        PRIMARY KEY(user_id, card_code)
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
    theme: str = "feuer"
    weight: int = 10
    weakness: str = ""
    art_path: str = ""

@dataclass
class IncidentCard:
    code: str
    name: str
    req: Dict[str, int]
    ew: int
    art_path: str = ""

# =========================================================
# CATALOG
# =========================================================

def vehicle_catalog():
    return [
        VehicleCard("V100","LHF",3,1,brand=4,technik=1,weakness="Erste Hilfe",art_path="assets/cards/vehicles/V100.png"),
        VehicleCard("V101","TLF",4,1,brand=5,weakness="Koordinierung",rarity="U",art_path="assets/cards/vehicles/V101.png"),
        VehicleCard("V102","DLK 23/12",3,1,hoehe=4,brand=1,weakness="Technik",rarity="U",art_path="assets/cards/vehicles/V102.png"),
        VehicleCard("V103","SW",3,1,brand=2,koord=1,weakness="Gefahrgut",art_path="assets/cards/vehicles/V103.png"),
        VehicleCard("V104","Feuerwehrkran",5,1,technik=6,weakness="Koordinierung",rarity="R",art_path="assets/cards/vehicles/V104.png"),
        VehicleCard("V105","ELW 1",2,1,koord=3,weakness="Brand",art_path="assets/cards/vehicles/V105.png"),
        VehicleCard("V106","ELW 2",3,1,koord=5,weakness="Rettung",rarity="R",art_path="assets/cards/vehicles/V106.png"),
        VehicleCard("V108","RTW",2,1,rettung=3,weakness="Feuer",theme="rd",art_path="assets/cards/vehicles/V108.png"),
        VehicleCard("V109","NEF",2,1,rettung=2,koord=1,weakness="Technik",theme="rd",art_path="assets/cards/vehicles/V109.png"),
        VehicleCard("V110","ITW",4,1,rettung=5,weakness="Koordinierung",rarity="U",theme="rd",art_path="assets/cards/vehicles/V110.png"),
        VehicleCard("V111","RTH",4,1,rettung=4,hoehe=1,weakness="Gefahrgut",rarity="U",theme="rd",art_path="assets/cards/vehicles/V111.png"),
        VehicleCard("V112","ITH",5,1,rettung=5,hoehe=1,weakness="Brand",rarity="R",theme="rd",art_path="assets/cards/vehicles/V112.png"),
    ]

def incident_catalog():
    return [
        IncidentCard("E001","Großbrand",{"brand":6},3,"assets/cards/incidents/E001.png"),
        IncidentCard("E002","Verkehrsunfall",{"technik":4},2,"assets/cards/incidents/E002.png"),
        IncidentCard("E003","Reanimation",{"rettung":4},3,"assets/cards/incidents/E003.png"),
        IncidentCard("E004","Gefahrgutunfall",{"technik":3},4,"assets/cards/incidents/E004.png"),
    ]

CATALOG = {c.code: c for c in vehicle_catalog()}
INCIDENTS = incident_catalog()

# =========================================================
# AUTH (einfach)
# =========================================================

def login(username):
    con = db()
    row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        con.execute("INSERT INTO users(username, coins) VALUES (?,?)", (username, START_COINS))
        con.commit()
        row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    con.close()
    return dict(row)

# =========================================================
# HELPERS
# =========================================================

def get_collection(uid):
    con = db()
    rows = con.execute("SELECT * FROM user_cards WHERE user_id=?", (uid,)).fetchall()
    con.close()
    return {r["card_code"]: r["qty"] for r in rows}

def add_cards(uid, codes):
    con = db()
    for code in codes:
        r = con.execute("SELECT qty FROM user_cards WHERE user_id=? AND card_code=?", (uid, code)).fetchone()
        if r:
            con.execute("UPDATE user_cards SET qty=qty+1 WHERE user_id=? AND card_code=?", (uid, code))
        else:
            con.execute("INSERT INTO user_cards VALUES (?,?,1)", (uid, code))
    con.commit()
    con.close()

# =========================================================
# UI
# =========================================================

if "user" not in st.session_state:
    st.session_state.user = None

st.sidebar.header("Account")
if not st.session_state.user:
    u = st.sidebar.text_input("Username")
    if st.sidebar.button("Login / Registrieren"):
        st.session_state.user = login(u)
        st.rerun()
else:
    st.sidebar.write(f"Angemeldet: **{st.session_state.user['username']}**")
    st.sidebar.write(f"Coins: **{st.session_state.user['coins']}**")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

if not st.session_state.user:
    st.stop()

uid = st.session_state.user["id"]

tabs = st.tabs(["Sammlung","Booster","Deck","Einsatz"])

# =========================================================
# SAMMLUNG
# =========================================================

with tabs[0]:
    st.subheader("Sammlung")
    coll = get_collection(uid)
    if not coll:
        st.info("Noch keine Karten.")
    for code, qty in coll.items():
        card = CATALOG.get(code)
        st.markdown(f"### {qty}× {card.name}")
        if os.path.exists(card.art_path):
            st.image(card.art_path, width=260)
        st.caption(f"EP {card.cost_ep} | Crew {card.crew} | Schwäche: {card.weakness}")
        st.divider()

# =========================================================
# BOOSTER
# =========================================================

with tabs[1]:
    st.subheader("Booster öffnen")
    if st.button("Feuer-Booster (25 Coins)"):
        cards = random.choices([c for c in CATALOG.values() if c.theme=="feuer"], k=5)
        add_cards(uid, [c.code for c in cards])
        st.success("Booster geöffnet")
        st.rerun()

# =========================================================
# DECK (Minimal)
# =========================================================

with tabs[2]:
    st.subheader("Deckbau (40 Karten – MVP)")
    st.info("Deckbau-UI kann als nächstes ausgebaut werden.")

# =========================================================
# EINSATZ
# =========================================================

with tabs[3]:
    if "incident" not in st.session_state:
        st.session_state.incident = random.choice(INCIDENTS)

    inc = st.session_state.incident
    st.subheader(inc.name)
    if os.path.exists(inc.art_path):
        st.image(inc.art_path, width=320)
    st.json(inc.req)
    st.write(f"EW: {inc.ew}")

    if st.button("Neuen Einsatz"):
        st.session_state.incident = random.choice(INCIDENTS)
        st.rerun()
