import streamlit as st
import os
import random
from dataclasses import dataclass
from typing import Dict, List

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="Berliner Feuerwehr TCG", layout="wide")
AXES = ["brand", "technik", "hoehe", "rettung", "koord"]

# =========================================================
# DATA MODELS
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
    theme: str = "feuer"
    rarity: str = "C"
    text: str = ""
    weakness: str = ""
    art_path: str = ""

    def stats(self):
        return {k: getattr(self, k) for k in AXES}


@dataclass
class IncidentCard:
    code: str
    name: str
    req: Dict[str, int]
    ew: int
    text: str
    art_path: str = ""


# =========================================================
# CARD CATALOG
# =========================================================

def vehicle_catalog():
    return [
        VehicleCard("V100","LHF",3,1,brand=4,technik=1,weakness="Erste Hilfe",
                    art_path="assets/cards/vehicles/V100.png"),
        VehicleCard("V101","TLF",4,1,brand=5,weakness="Koordinierung",
                    art_path="assets/cards/vehicles/V101.png"),
        VehicleCard("V102","DLK 23/12",3,1,hoehe=4,brand=1,weakness="Technik",
                    art_path="assets/cards/vehicles/V102.png"),
        VehicleCard("V103","SW",3,1,brand=2,koord=1,weakness="Gefahrgut",
                    art_path="assets/cards/vehicles/V103.png"),
        VehicleCard("V104","Feuerwehrkran",5,1,technik=6,weakness="Koordinierung",
                    art_path="assets/cards/vehicles/V104.png"),
        VehicleCard("V105","ELW 1",2,1,koord=3,weakness="Brand",
                    art_path="assets/cards/vehicles/V105.png"),
        VehicleCard("V106","ELW 2",3,1,koord=5,weakness="Rettung",
                    art_path="assets/cards/vehicles/V106.png"),
        VehicleCard("V108","RTW",2,1,rettung=3,weakness="Feuer",
                    art_path="assets/cards/vehicles/V108.png"),
        VehicleCard("V109","NEF",2,1,rettung=2,koord=1,weakness="Technik",
                    art_path="assets/cards/vehicles/V109.png"),
        VehicleCard("V110","ITW",4,1,rettung=5,weakness="Koordinierung",
                    art_path="assets/cards/vehicles/V110.png"),
        VehicleCard("V111","RTH",4,1,rettung=4,hoehe=1,weakness="Gefahrgut",
                    art_path="assets/cards/vehicles/V111.png"),
        VehicleCard("V112","ITH",5,1,rettung=5,hoehe=1,weakness="Brand",
                    art_path="assets/cards/vehicles/V112.png"),
    ]


def incident_catalog():
    return [
        IncidentCard("E001","Großbrand",{"brand":6},3,"Hohe Brandlast",
                     "assets/cards/incidents/E001.png"),
        IncidentCard("E002","Verkehrsunfall",{"technik":4},2,"Eingeklemmte Person",
                     "assets/cards/incidents/E002.png"),
        IncidentCard("E003","Reanimation",{"rettung":4},3,"Medizinischer Notfall",
                     "assets/cards/incidents/E003.png"),
        IncidentCard("E004","Gefahrgutunfall",{"technik":3},4,"Chemische Gefahr",
                     "assets/cards/incidents/E004.png"),
    ]


CATALOG = {c.code: c for c in vehicle_catalog()}
INCIDENTS = incident_catalog()

# =========================================================
# SESSION STATE
# =========================================================

if "hand" not in st.session_state:
    st.session_state.hand = random.sample(list(CATALOG.keys()), 5)

if "incident" not in st.session_state:
    st.session_state.incident = random.choice(INCIDENTS)

# =========================================================
# UI
# =========================================================

st.title("🚒 Berliner Feuerwehr TCG")

tab1, tab2 = st.tabs(["🃏 Hand", "🔥 Einsatz"])

# -----------------------------
# HAND TAB
# -----------------------------
with tab1:
    st.subheader("Deine Handkarten")

    for code in st.session_state.hand:
        card = CATALOG[code]

        st.markdown(f"### {card.name} ({card.code})")

        if os.path.exists(card.art_path):
            st.image(card.art_path, width=260)

        st.caption(
            f"EP {card.cost_ep} | Crew {card.crew} | "
            f"Brand {card.brand} · Technik {card.technik} · "
            f"Höhe {card.hoehe} · Rettung {card.rettung} · "
            f"Koord {card.koord} | Schwäche: {card.weakness}"
        )

        st.divider()

# -----------------------------
# EINSATZ TAB
# -----------------------------
with tab2:
    inc = st.session_state.incident

    st.subheader(f"Einsatz: {inc.name}")

    if os.path.exists(inc.art_path):
        st.image(inc.art_path, width=320)

    st.write("**Anforderungen:**")
    st.json(inc.req)

    st.write(f"**Einsatzwert (EW):** {inc.ew}")
    st.caption(inc.text)

    if st.button("Neuen Einsatz ziehen"):
        st.session_state.incident = random.choice(INCIDENTS)
        st.experimental_rerun()
