import json
import requests
import streamlit as st

API_BASE = st.secrets.get("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Berliner Feuerwehr TCG", layout="wide")
st.title("Berliner Feuerwehr TCG – Online (MVP)")

# -------------------------
# Helpers
# -------------------------

def api_headers():
    token = st.session_state.get("token")
    return {"X-Token": token} if token else {}

def api_get(path, params=None):
    r = requests.get(f"{API_BASE}{path}", headers=api_headers(), params=params, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def api_post(path, payload):
    r = requests.post(f"{API_BASE}{path}", headers=api_headers(), json=payload, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

# -------------------------
# Auth UI
# -------------------------

if "token" not in st.session_state:
    st.session_state.token = None
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

with st.sidebar:
    st.header("Account")

    if not st.session_state.token:
        tab1, tab2 = st.tabs(["Login", "Registrieren"])

        with tab1:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Passwort", type="password", key="login_p")
            if st.button("Login"):
                data = requests.post(f"{API_BASE}/auth/login", json={"username": u, "password": p}, timeout=15).json()
                if "token" not in data:
                    st.error(data)
                else:
                    st.session_state.token = data["token"]
                    st.success("Eingeloggt.")
                    st.rerun()

        with tab2:
            u2 = st.text_input("Username", key="reg_u")
            p2 = st.text_input("Passwort", type="password", key="reg_p")
            if st.button("Account erstellen"):
                r = requests.post(f"{API_BASE}/auth/register", json={"username": u2, "password": p2}, timeout=15)
                if r.status_code >= 400:
                    st.error(r.text)
                else:
                    st.success("Registriert. Bitte einloggen.")

    else:
        me = api_get("/me")
        st.write(f"Angemeldet als: **{me['username']}**")
        st.write(f"Coins: **{me['coins']}**")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.room_code = ""
            st.rerun()

if not st.session_state.token:
    st.info("Bitte zuerst einloggen/registrieren.")
    st.stop()

# -------------------------
# Main Tabs
# -------------------------

t_collection, t_boosters, t_rooms, t_match = st.tabs(["Sammlung", "Booster", "Räume", "Duell"])

with t_collection:
    st.subheader("Ihre Sammlung")
    data = api_get("/collection")
    cards = data.get("cards", [])
    if not cards:
        st.caption("Noch keine Karten. Kaufen Sie Booster.")
    else:
        # simple list
        for c in cards:
            st.write(f"{c['qty']}× {c['name']} ({c['theme']}, {c['rarity']})")

with t_boosters:
    st.subheader("Booster kaufen & öffnen")
    col1, col2, col3 = st.columns(3)

    def buy(theme: str):
        res = api_post("/booster/buy_open", {"theme": theme})
        st.success(f"Booster '{theme}' geöffnet. Coins: {res['coins']}")
        st.json(res["cards"])

    with col1:
        st.markdown("### Feuer-Booster")
        st.caption("Feuerwehr-Fokus (Brand/Höhe/Gefahrgut).")
        if st.button("Feuer-Booster kaufen (25 Coins)"):
            buy("feuer")

    with col2:
        st.markdown("### Rettungsdienst-Booster")
        st.caption("RD-Fokus (rettung/koord).")
        if st.button("RD-Booster kaufen (25 Coins)"):
            buy("rd")

    with col3:
        st.markdown("### THL-Booster")
        st.caption("Technische Hilfeleistung (technik/koord).")
        if st.button("THL-Booster kaufen (25 Coins)"):
            buy("thl")

with t_rooms:
    st.subheader("Duellräume")
    r1, r2 = st.columns(2)

    with r1:
        st.markdown("### Raum erstellen")
        custom = st.text_input("Optionaler Raumcode", value="")
        if st.button("Erstellen"):
            res = api_post("/room/create", {"room_code": custom or None})
            st.session_state.room_code = res["room_code"]
            st.success(f"Raum erstellt: {res['room_code']}")

    with r2:
        st.markdown("### Raum beitreten")
        join_code = st.text_input("Raumcode", value=st.session_state.room_code)
        if st.button("Beitreten"):
            res = api_post("/room/join", {"room_code": join_code})
            st.session_state.room_code = res["room_code"]
            st.success(f"Beigetreten: {res['room_code']}")

    if st.session_state.room_code:
        st.divider()
        status = api_get("/room/status", params={"room_code": st.session_state.room_code})
        st.write(f"Aktueller Raum: **{status['room_code']}**")
        st.write("Spieler:")
        for p in status["players"]:
            st.write(f"- {p['username']} (id={p['id']})")
        if st.button("Match starten (MVP: genau 2 Spieler)"):
            api_post("/match/start", {"room_code": st.session_state.room_code})
            st.success("Match gestartet.")
            st.rerun()

with t_match:
    st.subheader("Duell (MVP Turnbased)")
    if not st.session_state.room_code:
        st.info("Bitte zuerst einen Raum erstellen/beitreten.")
        st.stop()

    # fetch state
    state = api_get("/match/state", params={"room_code": st.session_state.room_code})
    me = api_get("/me")
    my_id = me["user_id"]

    st.write(f"Runde: {state['round_no']} | Phase: **{state['phase']}** | Druck: {state['pressure']}/{state['pressure_max']}")
    st.write(f"Aktiver Spieler: {state['active_player']}")

    my = state["players"].get(str(my_id))
    if not my:
        st.error("Sie sind nicht Teil dieses Matches (oder Raum/Token mismatch).")
        st.stop()

    st.write(f"Ihre Ressourcen: EP={my['ep']} | Crew={my['crew']} | EW={my['ew']}")
    st.divider()

    # incidents
    cols = st.columns(2)
    for i in [0, 1]:
        with cols[i]:
            inc = state["open_incidents"][i]
            st.markdown(f"### Slot {i+1}: {inc['name']}")
            st.write(f"Zeit: {inc['time_left']} | EW: {inc['ew']}")
            st.write("Anforderungen:")
            st.json({k: v for k, v in inc["req"].items() if v > 0})

    st.divider()

    # Hand & assign
    st.markdown("## Ihre Hand (Fahrzeuge)")
    if not my["hand"]:
        st.caption("Keine Karten auf der Hand.")
    else:
        selected = st.selectbox("Karte wählen (card_code)", my["hand"])
        slot = st.radio("Slot", [0, 1], horizontal=True)

        if st.button("Zuweisen (nur in Planung & wenn Sie dran sind)"):
            try:
                api_post("/match/assign", {"room_code": st.session_state.room_code, "slot": slot, "card_code": selected})
                st.success("Zugewiesen.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    if st.button("Phase weiter"):
        try:
            api_post("/match/advance_phase", {"room_code": st.session_state.room_code})
            st.rerun()
        except Exception as e:
            st.error(str(e))

    with st.expander("Log"):
        for line in state.get("log", [])[-30:]:
            st.write(line)
