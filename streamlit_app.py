import streamlit as st
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ==========================================================
# Models
# ==========================================================

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

    def power(self) -> Dict[str, int]:
        return {
            "brand": self.brand,
            "technik": self.technik,
            "hoehe": self.hoehe,
            "gefahrgut": self.gefahrgut,
        }


@dataclass
class IncidentCard:
    id: str
    name: str
    req_brand: int = 0
    req_technik: int = 0
    req_hoehe: int = 0
    req_gefahrgut: int = 0
    time_left: int = 2
    ew: int = 3
    escalation_text: str = ""
    tags: List[str] = field(default_factory=list)

    def reqs(self) -> Dict[str, int]:
        return {
            "brand": self.req_brand,
            "technik": self.req_technik,
            "hoehe": self.req_hoehe,
            "gefahrgut": self.req_gefahrgut,
        }


@dataclass
class ActionCard:
    id: str
    name: str
    kind: str  # "taktik" or "ereignis"
    text: str


@dataclass
class PlayerState:
    pid: str
    name: str
    ep: int = 6
    crew: int = 5
    ew_points: int = 0
    hand_vehicles: List[VehicleCard] = field(default_factory=list)
    hand_actions: List[ActionCard] = field(default_factory=list)


@dataclass
class GameState:
    round_no: int = 1
    active_idx: int = 0
    started: bool = False

    # Global pressure
    pressure: int = 0
    pressure_max: int = 12

    players: List[PlayerState] = field(default_factory=list)

    vehicle_deck: List[VehicleCard] = field(default_factory=list)
    vehicle_discard: List[VehicleCard] = field(default_factory=list)

    incident_deck: List[IncidentCard] = field(default_factory=list)
    incident_discard: List[IncidentCard] = field(default_factory=list)

    action_deck: List[ActionCard] = field(default_factory=list)
    action_discard: List[ActionCard] = field(default_factory=list)

    open_incidents: List[Optional[IncidentCard]] = field(default_factory=lambda: [None, None])

    # Assignments: incident_slot -> list of (pid, card)
    assignments: Dict[int, List[Tuple[str, VehicleCard]]] = field(default_factory=lambda: {0: [], 1: []})

    # per-turn restriction: each player may assign at most 1 vehicle per turn (test rule)
    assigned_this_turn: Dict[str, bool] = field(default_factory=dict)

    # per-turn / round effects
    effect_double_assign: Dict[str, bool] = field(default_factory=dict)  # Kräfte bündeln
    effect_fast_deploy: Dict[str, bool] = field(default_factory=dict)    # Schneller Aufbau
    effect_ignore_escalation_this_round: bool = False                    # Klare Befehlslage
    global_block_tactics_this_round: bool = False                        # Funkstörung


# ==========================================================
# Data pools
# ==========================================================

def make_vehicle_pool() -> List[VehicleCard]:
    cards = [
        VehicleCard("V001", "HLF 20", 4, 1, brand=4, technik=3, text="+1 Technik bei Verkehrsunfall (später)"),
        VehicleCard("V002", "LF 20", 3, 1, brand=4, technik=1, text="+1 Brand mit weiterem Löschfahrzeug (später)"),
        VehicleCard("V003", "DLK 23/12", 3, 1, hoehe=4, brand=1, text="Pflicht bei Hochhausbrand (später)"),
        VehicleCard("V004", "RW", 4, 1, technik=5, text="Doppelt bei eingeklemmter Person (später)"),
        VehicleCard("V005", "ELW 1", 2, 1, text="1×/Einsatz: -1 EP Kosten (später)"),
        VehicleCard("V006", "GW-Gefahrgut", 4, 1, gefahrgut=5, text="Verhindert Eskalation bei Gefahrgut (später)"),
        VehicleCard("V007", "TM 50", 4, 1, hoehe=5, text="Kann DLK ersetzen (später)"),
        VehicleCard("V008", "GW-Atemschutz", 3, 1, text="Verhindert Personalverlust (später)"),
        VehicleCard("V009", "Feuerwehrkran", 5, 1, technik=6, text="Pflicht bei Bauunfall (später)"),
        VehicleCard("V010", "WLF", 3, 1, text="Aktivierung +1 EP: kopiert GW (später)"),
    ]
    return cards * 3


def make_incident_deck() -> List[IncidentCard]:
    incidents = [
        IncidentCard("I001", "Wohnungsbrand", req_brand=6, time_left=2, ew=3,
                     escalation_text="Anforderungen +1 Brand, Druck +1", tags=["brand"]),
        IncidentCard("I002", "Verkehrsunfall – eingeklemmte Person", req_technik=5, time_left=2, ew=3,
                     escalation_text="Druck +2", tags=["technik", "vu"]),
        IncidentCard("I003", "Hochhausbrand", req_brand=5, req_hoehe=4, time_left=3, ew=5,
                     escalation_text="Anforderungen +1, Druck +2", tags=["brand", "hoehe"]),
        IncidentCard("I004", "Gefahrgutunfall", req_gefahrgut=4, time_left=2, ew=4,
                     escalation_text="Druck +2 (Gefahrgut)", tags=["gefahrgut"]),
        IncidentCard("I005", "Bauunfall", req_technik=6, time_left=3, ew=4,
                     escalation_text="Anforderungen +1 Technik, Druck +1", tags=["technik"]),
        IncidentCard("I006", "Unwetterlage (Großeinsatz)", req_technik=4, time_left=3, ew=6,
                     escalation_text="Druck +2 (Großeinsatz)", tags=["technik", "gross"]),
    ]
    return incidents * 2


def make_action_deck() -> List[ActionCard]:
    cards = [
        ActionCard("A001", "Nachalarmierung", "taktik", "Erhalte sofort +2 EP."),
        ActionCard("A002", "Klare Befehlslage", "taktik", "Die nächste Eskalationsphase wird ignoriert."),
        ActionCard("A003", "Abschnittsbildung", "taktik", "Auf einem Einsatz: größte Anforderung -2 (min 0), kleinste Anforderung +1."),
        ActionCard("A004", "Priorisierung", "taktik", "Auf einem Einsatz: Zeitlimit +1."),
        ActionCard("A005", "Kräfte bündeln", "taktik", "Dein nächstes zugewiesenes Fahrzeug zählt doppelt in der Einsatzphase."),
        ActionCard("A006", "Lage unter Kontrolle", "taktik", "Einsatzdruck -1."),
        ActionCard("A007", "Reserve aktivieren", "taktik", "Personal +1."),
        ActionCard("A008", "Schneller Aufbau", "taktik", "Deine nächste Fahrzeugzuweisung kostet -1 EP."),
        ActionCard("E009", "Funkstörung", "ereignis", "Diese Runde dürfen keine Taktikkarten gespielt werden."),
        ActionCard("E010", "Materialausfall", "ereignis", "Vereinfacht: Beim nächsten Resolve Hinweis im Log (v1.2 präzisieren)."),
        ActionCard("E011", "Medieninteresse", "ereignis", "Der nächste erfüllte Einsatz gibt +1 EW extra (global)."),
        ActionCard("E012", "Unklare Lage", "ereignis", "Anforderungen sind bis zur Einsatzphase verdeckt."),
    ]
    return cards * 2


# ==========================================================
# Helpers
# ==========================================================

def active_player(gs: GameState) -> PlayerState:
    return gs.players[gs.active_idx % len(gs.players)]


def pressure_cost_modifier(gs: GameState) -> int:
    return 1 if gs.pressure >= 5 else 0


def crew_regen_modifier(gs: GameState) -> int:
    return -1 if gs.pressure >= 8 else 0


def draw_vehicle(gs: GameState) -> VehicleCard:
    if not gs.vehicle_deck:
        gs.vehicle_deck = gs.vehicle_discard
        gs.vehicle_discard = []
        random.shuffle(gs.vehicle_deck)
    return gs.vehicle_deck.pop()


def draw_incident(gs: GameState) -> Optional[IncidentCard]:
    if not gs.incident_deck:
        return None
    return gs.incident_deck.pop()


def draw_action(gs: GameState) -> ActionCard:
    if not gs.action_deck:
        gs.action_deck = gs.action_discard
        gs.action_discard = []
        random.shuffle(gs.action_deck)
    return gs.action_deck.pop()


def requirements_met(req: Dict[str, int], total: Dict[str, int]) -> bool:
    for k, v in req.items():
        if total.get(k, 0) < v:
            return False
    return True


def add_requirements_only_where_needed(inc: IncidentCard, delta: int) -> None:
    if inc.req_brand > 0:
        inc.req_brand += delta
    if inc.req_technik > 0:
        inc.req_technik += delta
    if inc.req_hoehe > 0:
        inc.req_hoehe += delta
    if inc.req_gefahrgut > 0:
        inc.req_gefahrgut += delta


# ==========================================================
# Core game flow (v1.1 + actions)
# ==========================================================

def init_game() -> GameState:
    gs = GameState()
    gs.started = True

    gs.players = [
        PlayerState("P1", "Spieler 1"),
        PlayerState("P2", "Spieler 2"),
    ]

    gs.assigned_this_turn = {p.pid: False for p in gs.players}
    gs.effect_double_assign = {p.pid: False for p in gs.players}
    gs.effect_fast_deploy = {p.pid: False for p in gs.players}

    gs.vehicle_deck = make_vehicle_pool()
    random.shuffle(gs.vehicle_deck)

    gs.incident_deck = make_incident_deck()
    random.shuffle(gs.incident_deck)

    gs.action_deck = make_action_deck()
    random.shuffle(gs.action_deck)

    for p in gs.players:
        p.ep = 6
        p.crew = 5
        p.ew_points = 0
        p.hand_vehicles = [draw_vehicle(gs) for _ in range(5)]
        p.hand_actions = [draw_action(gs) for _ in range(2)]

    gs.open_incidents[0] = draw_incident(gs)
    gs.open_incidents[1] = draw_incident(gs)

    gs.assignments = {0: [], 1: []}

    start_turn(gs)
    return gs


def start_turn(gs: GameState) -> None:
    ap = active_player(gs)

    ap.ep = min(10, ap.ep + 2)

    regen = 1 + crew_regen_modifier(gs)
    if regen < 0:
        regen = 0
    ap.crew = min(7, ap.crew + regen)

    gs.assigned_this_turn[ap.pid] = False


def end_turn(gs: GameState) -> None:
    gs.active_idx = (gs.active_idx + 1) % len(gs.players)

    if gs.active_idx == 0:
        gs.round_no += 1
        gs.global_block_tactics_this_round = False
        gs.effect_ignore_escalation_this_round = False
        st.session_state.media_bonus_next_resolve = False
        st.session_state.unclear_incidents_this_round = False
        st.session_state.material_failure_next_resolve = False

    start_turn(gs)


def assign_vehicle_to_incident(gs: GameState, pid: str, card_id: str, slot: int) -> Tuple[bool, str]:
    p = next((x for x in gs.players if x.pid == pid), None)
    if p is None:
        return False, "Unbekannter Spieler."

    if gs.assigned_this_turn.get(pid, False):
        return False, "Pro Zug darf nur 1 Fahrzeug zugewiesen werden (Testregel)."

    inc = gs.open_incidents[slot]
    if inc is None:
        return False, "Kein Einsatz in diesem Slot."

    card = next((c for c in p.hand_vehicles if c.id == card_id), None)
    if card is None:
        return False, "Karte nicht auf der Hand."

    cost = card.cost_ep + pressure_cost_modifier(gs)
    if gs.effect_fast_deploy.get(pid, False):
        cost = max(0, cost - 1)

    if p.ep < cost:
        return False, f"Nicht genug EP. Benötigt: {cost}."

    if p.crew < card.crew:
        return False, "Nicht genug Personal."

    p.ep -= cost
    p.crew -= card.crew
    p.hand_vehicles.remove(card)

    gs.assignments[slot].append((pid, card))
    gs.assigned_this_turn[pid] = True

    if gs.effect_fast_deploy.get(pid, False):
        gs.effect_fast_deploy[pid] = False

    return True, f"{card.name} zu '{inc.name}' zugewiesen (Kosten: {cost} EP)."


def resolve_incidents(gs: GameState) -> List[str]:
    logs: List[str] = []
    media_bonus = st.session_state.media_bonus_next_resolve

    for slot in [0, 1]:
        inc = gs.open_incidents[slot]
        if inc is None:
            continue

        assigned = gs.assignments.get(slot, [])
        total = {"brand": 0, "technik": 0, "hoehe": 0, "gefahrgut": 0}
        contrib: Dict[str, int] = {}

        for pid, card in assigned:
            mult = 2 if gs.effect_double_assign.get(pid, False) else 1
            pw = card.power()
            for k in total.keys():
                total[k] += pw.get(k, 0) * mult
            contrib[pid] = contrib.get(pid, 0) + sum(pw.values()) * mult

        for pid in list(gs.effect_double_assign.keys()):
            gs.effect_double_assign[pid] = False

        req = inc.reqs()
        met = requirements_met(req, total)

        logs.append(f"[Einsatzphase] Slot {slot+1}: '{inc.name}'")
        logs.append(f"  Anforderungen: {req} | Erreicht: {total}")

        if met:
            extra = 1 if media_bonus else 0
            if contrib:
                winner_pid = max(contrib.items(), key=lambda x: x[1])[0]
                winner = next(p for p in gs.players if p.pid == winner_pid)
                winner.ew_points += (inc.ew + extra)

                helpers = [pid for pid in contrib.keys() if pid != winner_pid]
                for hid in helpers:
                    hp = next(p for p in gs.players if p.pid == hid)
                    hp.ep = min(10, hp.ep + 1)

                logs.append(f"  Ergebnis: ERFÜLLT. {winner.name} erhält {inc.ew}+{extra} EW.")
                if helpers:
                    logs.append("  Mitwirkungsbonus: Helfer erhalten +1 EP.")
            else:
                logs.append("  Ergebnis: ERFÜLLT (ohne Zuordnung) – keine Punkte.")

            gs.incident_discard.append(inc)
            gs.open_incidents[slot] = draw_incident(gs)
        else:
            logs.append("  Ergebnis: NICHT erfüllt. Eskalation folgt (sofern nicht verhindert).")

        for _, card in assigned:
            gs.vehicle_discard.append(card)
        gs.assignments[slot] = []

    if media_bonus:
        st.session_state.media_bonus_next_resolve = False
    st.session_state.unclear_incidents_this_round = False

    if st.session_state.material_failure_next_resolve:
        logs.append("  Hinweis: Materialausfall war aktiv (Effekt in v1.2 präzisieren).")
        st.session_state.material_failure_next_resolve = False

    return logs


def escalation_phase(gs: GameState) -> List[str]:
    logs: List[str] = []

    if gs.effect_ignore_escalation_this_round:
        logs.append("[Eskalation] Klare Befehlslage aktiv: Eskalation wird ignoriert.")
        gs.effect_ignore_escalation_this_round = False
        return logs

    for slot in [0, 1]:
        inc = gs.open_incidents[slot]
        if inc is None:
            continue

        inc.time_left -= 1
        gs.pressure += 1
        logs.append(f"[Eskalation] Slot {slot+1}: '{inc.name}' Zeitlimit -> {inc.time_left}. Druck -> {gs.pressure}.")

        if inc.time_left <= 0:
            add_requirements_only_where_needed(inc, 1)
            extra_pressure = 2 if any(t in inc.tags for t in ["gefahrgut", "hoehe", "vu", "gross"]) else 1
            gs.pressure += extra_pressure
            inc.time_left = 2
            logs.append(f"  Eskalation: Anforderungen +1. Zusatzdruck +{extra_pressure} -> {gs.pressure}. Zeitlimit reset auf 2.")
            logs.append(f"  Hinweis: {inc.escalation_text}")

    if gs.pressure < 0:
        gs.pressure = 0

    return logs


# ==========================================================
# Actions
# ==========================================================

def play_taktik(gs: GameState, pid: str, action_id: str, target_slot: Optional[int]) -> Tuple[bool, str]:
    if gs.global_block_tactics_this_round:
        return False, "Funkstörung aktiv: Diese Runde dürfen keine Taktikkarten gespielt werden."

    p = next((x for x in gs.players if x.pid == pid), None)
    if not p:
        return False, "Unbekannter Spieler."

    card = next((a for a in p.hand_actions if a.id == action_id and a.kind == "taktik"), None)
    if not card:
        return False, "Taktikkarte nicht auf der Hand."

    name = card.name

    if name == "Nachalarmierung":
        p.ep = min(10, p.ep + 2)
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Nachalarmierung: +2 EP."

    if name == "Reserve aktivieren":
        p.crew = min(7, p.crew + 1)
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Reserve aktivieren: +1 Personal."

    if name == "Lage unter Kontrolle":
        gs.pressure = max(0, gs.pressure - 1)
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Lage unter Kontrolle: Einsatzdruck -1."

    if name == "Schneller Aufbau":
        gs.effect_fast_deploy[pid] = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Schneller Aufbau: Nächste Fahrzeugzuweisung kostet -1 EP."

    if name == "Kräfte bündeln":
        gs.effect_double_assign[pid] = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Kräfte bündeln: Nächstes zugewiesenes Fahrzeug zählt doppelt."

    if name == "Klare Befehlslage":
        gs.effect_ignore_escalation_this_round = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Klare Befehlslage: Nächste Eskalationsphase wird ignoriert."

    if name == "Priorisierung":
        if target_slot is None:
            return False, "Priorisierung benötigt ein Slot-Ziel."
        inc = gs.open_incidents[target_slot]
        if not inc:
            return False, "Kein Einsatz in diesem Slot."
        inc.time_left += 1
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, f"Priorisierung: Zeitlimit von '{inc.name}' +1."

    if name == "Abschnittsbildung":
        if target_slot is None:
            return False, "Abschnittsbildung benötigt ein Slot-Ziel."
        inc = gs.open_incidents[target_slot]
        if not inc:
            return False, "Kein Einsatz in diesem Slot."

        req = inc.reqs()
        nonzero = [(k, v) for k, v in req.items() if v > 0]
        if not nonzero:
            return False, "Dieser Einsatz hat keine Anforderungen."

        largest_k, largest_v = max(nonzero, key=lambda x: x[1])
        smallest_k, smallest_v = min(nonzero, key=lambda x: x[1])

        def set_req(k: str, val: int) -> None:
            if k == "brand":
                inc.req_brand = val
            elif k == "technik":
                inc.req_technik = val
            elif k == "hoehe":
                inc.req_hoehe = val
            elif k == "gefahrgut":
                inc.req_gefahrgut = val

        set_req(largest_k, max(0, largest_v - 2))
        set_req(smallest_k, smallest_v + 1)

        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, f"Abschnittsbildung auf '{inc.name}': {largest_k} -2, {smallest_k} +1."

    return False, "Taktik ist (noch) nicht implementiert."


def trigger_event(gs: GameState, pid: str, event_id: str) -> Tuple[bool, str]:
    p = next((x for x in gs.players if x.pid == pid), None)
    if not p:
        return False, "Unbekannter Spieler."

    card = next((a for a in p.hand_actions if a.id == event_id and a.kind == "ereignis"), None)
    if not card:
        return False, "Ereignis nicht auf der Hand."

    if event_id == "E009":
        gs.global_block_tactics_this_round = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Ereignis Funkstörung: Taktikkarten diese Runde blockiert."

    if event_id == "E011":
        st.session_state.media_bonus_next_resolve = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Ereignis Medieninteresse: Nächster erfüllter Einsatz gibt +1 EW."

    if event_id == "E012":
        st.session_state.unclear_incidents_this_round = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Ereignis Unklare Lage: Anforderungen bis zur Einsatzphase verdeckt."

    if event_id == "E010":
        st.session_state.material_failure_next_resolve = True
        p.hand_actions.remove(card)
        gs.action_discard.append(card)
        return True, "Ereignis Materialausfall: Effekt vereinfacht, wird beim nächsten Resolve protokolliert."

    return False, "Unbekanntes Ereignis."


# ==========================================================
# Streamlit UI
# ==========================================================

st.set_page_config(page_title="Einsatzleitung Berlin – Prototyp", layout="wide")

if "media_bonus_next_resolve" not in st.session_state:
    st.session_state.media_bonus_next_resolve = False
if "unclear_incidents_this_round" not in st.session_state:
    st.session_state.unclear_incidents_this_round = False
if "material_failure_next_resolve" not in st.session_state:
    st.session_state.material_failure_next_resolve = False
if "last_logs" not in st.session_state:
    st.session_state.last_logs = []

st.title("Einsatzleitung Berlin – Online-Prototyp (Streamlit, v1.1)")

if "gs" not in st.session_state:
    st.session_state.gs = init_game()

gs: GameState = st.session_state.gs
ap = active_player(gs)

# Global loss check
if gs.pressure >= gs.pressure_max:
    st.error("Gemeinsame Niederlage: Einsatzdruck hat das Maximum erreicht.")
    if st.button("Neues Spiel starten"):
        st.session_state.gs = init_game()
        st.session_state.last_logs = []
        st.rerun()
    st.stop()

# Header
colA, colB, colC, colD = st.columns([1.2, 1, 1, 1])
with colA:
    st.subheader("Status")
    st.write(f"Runde: {gs.round_no}")
    st.write(f"Aktiver Spieler: {ap.name}")

with colB:
    st.subheader("Einsatzdruck")
    st.write(f"{gs.pressure} / {gs.pressure_max}")
    if gs.pressure >= 8:
        st.warning("Druck 8+: Personal-Regeneration -1")
    elif gs.pressure >= 5:
        st.warning("Druck 5+: Fahrzeugzuweisung kostet +1 EP")

with colC:
    st.subheader("EW")
    for p in gs.players:
        st.write(f"{p.name}: {p.ew_points}")

with colD:
    st.subheader("Kontrolle")
    if st.button("Neues Spiel"):
        st.session_state.gs = init_game()
        st.session_state.last_logs = []
        st.session_state.media_bonus_next_resolve = False
        st.session_state.unclear_incidents_this_round = False
        st.session_state.material_failure_next_resolve = False
        st.rerun()

st.divider()

# Incidents Board
st.subheader("Einsatz-Board (2 offene Einsätze)")
board_cols = st.columns(2)

def render_incident(slot: int) -> None:
    inc = gs.open_incidents[slot]
    if inc is None:
        st.info("Kein weiterer Einsatz im Deck.")
        return

    st.markdown(f"### Slot {slot+1}: {inc.name}")
    st.write(f"Zeitlimit: {inc.time_left} | Einsatzwert (EW): {inc.ew}")

    if st.session_state.unclear_incidents_this_round:
        st.write("Anforderungen: verdeckt (Unklare Lage).")
    else:
        req = {k: v for k, v in inc.reqs().items() if v > 0}
        st.write("Anforderungen:")
        st.json(req)

    assigned = gs.assignments.get(slot, [])
    if assigned:
        st.write("Zugewiesene Fahrzeuge (diese Runde):")
        for pid, card in assigned:
            pname = next(p.name for p in gs.players if p.pid == pid)
            st.write(f"- {pname}: {card.name} (B {card.brand} | T {card.technik} | H {card.hoehe} | G {card.gefahrgut})")
    else:
        st.write("Zugewiesen: noch nichts.")

for i, c in enumerate(board_cols):
    with c:
        render_incident(i)

st.divider()

# Player area
left, mid, right = st.columns([1.2, 1, 1])

with left:
    st.subheader(f"Zug: {ap.name}")
    st.write(f"EP: {ap.ep} | Personal: {ap.crew}")

    if gs.global_block_tactics_this_round:
        st.info("Funkstörung aktiv: Taktikkarten bis Rundenende blockiert.")
    if st.session_state.media_bonus_next_resolve:
        st.info("Medieninteresse aktiv: Nächster erfüllter Einsatz gibt +1 EW.")
    if st.session_state.material_failure_next_resolve:
        st.info("Materialausfall aktiv: Beim nächsten Resolve wird ein Hinweis protokolliert.")
    if st.session_state.unclear_incidents_this_round:
        st.info("Unklare Lage aktiv: Anforderungen verdeckt bis zur Einsatzphase.")

    st.markdown("### Karte ziehen")
    draw_type = st.radio("Zieh-Typ", ["Fahrzeug", "Taktik/Ereignis"], horizontal=True)
    if st.button("Ziehen"):
        if draw_type == "Fahrzeug":
            ap.hand_vehicles.append(draw_vehicle(gs))
            st.session_state.last_logs = ["[System] 1 Fahrzeugkarte gezogen."]
        else:
            ap.hand_actions.append(draw_action(gs))
            st.session_state.last_logs = ["[System] 1 Aktionskarte gezogen."]
        st.rerun()

with mid:
    st.subheader("Fahrzeug zuweisen")
    if not ap.hand_vehicles:
        st.info("Keine Fahrzeugkarten auf der Hand.")
    else:
        labels = [f"{c.id} – {c.name} (EP {c.cost_ep}, Pers {c.crew})" for c in ap.hand_vehicles]
        sel_idx = st.selectbox("Fahrzeugkarte", range(len(labels)), format_func=lambda i: labels[i])
        sel_card = ap.hand_vehicles[sel_idx]

        slot = st.radio("Ziel-Slot", [0, 1], format_func=lambda x: f"Slot {x+1}", horizontal=True)

        cost = sel_card.cost_ep + pressure_cost_modifier(gs)
        if gs.effect_fast_deploy.get(ap.pid, False):
            cost = max(0, cost - 1)

        st.write(f"Kosten: {cost} EP | Personal: {sel_card.crew}")
        if sel_card.text:
            st.caption(sel_card.text)

        if st.button("Zuweisen"):
            ok, msg = assign_vehicle_to_incident(gs, ap.pid, sel_card.id, slot)
            st.session_state.last_logs = [msg]
            st.rerun()

with right:
    st.subheader("Taktik / Ereignisse")

    taktiks = [a for a in ap.hand_actions if a.kind == "taktik"]
    events = [a for a in ap.hand_actions if a.kind == "ereignis"]

    st.markdown("### Taktikkarten (Hand)")
    if not taktiks:
        st.caption("Keine Taktikkarten auf der Hand.")
    else:
        tlabels = [f"{a.id} – {a.name}" for a in taktiks]
        tsel = st.selectbox("Taktik wählen", range(len(tlabels)), format_func=lambda i: tlabels[i], key="tsel")
        tcard = taktiks[tsel]
        st.write(tcard.text)

        t_target_slot: Optional[int] = None
        if tcard.name in {"Priorisierung", "Abschnittsbildung"}:
            t_target_slot = st.radio("Taktik-Ziel", [0, 1], format_func=lambda x: f"Slot {x+1}", horizontal=True, key="t_target")

        if st.button("Taktik spielen"):
            ok, msg = play_taktik(gs, ap.pid, tcard.id, t_target_slot)
            st.session_state.last_logs = [msg]
            st.rerun()

    st.markdown("### Ereignisse (Hand, global)")
    if not events:
        st.caption("Keine Ereignisse auf der Hand.")
    else:
        elabels = [f"{a.id} – {a.name}" for a in events]
        esel = st.selectbox("Ereignis wählen", range(len(elabels)), format_func=lambda i: elabels[i], key="esel")
        ecard = events[esel]
        st.write(ecard.text)

        if st.button("Ereignis auslösen"):
            ok, msg = trigger_event(gs, ap.pid, ecard.id)
            st.session_state.last_logs = [msg]
            st.rerun()

st.divider()

# Phases
st.subheader("Phasensteuerung (Test)")
pcol1, pcol2, pcol3 = st.columns(3)

with pcol1:
    if st.button("Einsatzphase auswerten"):
        st.session_state.last_logs = resolve_incidents(gs)
        st.rerun()

with pcol2:
    if st.button("Eskalationsphase durchführen"):
        st.session_state.last_logs = escalation_phase(gs)
        st.rerun()

with pcol3:
    if st.button("Zug beenden"):
        end_turn(gs)
        st.session_state.last_logs = ["[System] Zug beendet. Ressourcenphase für nächsten Spieler ausgeführt."]
        st.rerun()

# Logs
st.subheader("Protokoll")
if st.session_state.last_logs:
    for line in st.session_state.last_logs:
        st.write(line)
else:
    st.caption("Noch keine Aktionen protokolliert.")

# Debug
with st.expander("Debug: Spielzustand"):
    st.write({
        "round_no": gs.round_no,
        "active_player": ap.name,
        "pressure": gs.pressure,
        "players": [
            {
                "name": p.name,
                "ep": p.ep,
                "crew": p.crew,
                "ew": p.ew_points,
                "hand_vehicles": [c.id for c in p.hand_vehicles],
                "hand_actions": [a.id for a in p.hand_actions],
            }
            for p in gs.players
        ],
        "open_incidents": [inc.name if inc else None for inc in gs.open_incidents],
        "incident_reqs": [inc.reqs() if inc else None for inc in gs.open_incidents],
        "assignments": {slot: [(pid, card.id) for pid, card in lst] for slot, lst in gs.assignments.items()},
        "flags": {
            "block_tactics": gs.global_block_tactics_this_round,
            "ignore_escalation": gs.effect_ignore_escalation_this_round,
            "media_bonus_next_resolve": st.session_state.media_bonus_next_resolve,
            "unclear_incidents_this_round": st.session_state.unclear_incidents_this_round,
            "material_failure_next_resolve": st.session_state.material_failure_next_resolve,
            "fast_deploy": gs.effect_fast_deploy,
            "double_assign": gs.effect_double_assign,
        }
    })
