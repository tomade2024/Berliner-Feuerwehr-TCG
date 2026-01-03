import os
import requests
import streamlit as st

API_BASE = st.secrets.get("API_BASE", os.environ.get("API_BASE", "http://127.0.0.1:8000"))

def backend_healthcheck():
    try:
        r = requests.get(f"{API_BASE}/catalog/vehicles", timeout=3)
        return (r.status_code < 500), f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

ok, info = backend_healthcheck()

with st.sidebar:
    st.caption("Backend Status")
    st.write(f"API_BASE: {API_BASE}")
    if ok:
        st.success(f"Backend erreichbar ({info})")
    else:
        st.error(f"Backend NICHT erreichbar: {info}")
        st.stop()

# -------------------------
# Helpers
# -------------------------

def api_headers():
    token = st.session_state.get("token")
    return {"X-Token": token} if token else {}

def api_get(path, params=None):
    r = requests.get(f"{API_BASE}{path}", headers=api_headers(), params=params, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def api_post(path, payload):
    r = requests.post(f"{API_BASE}{path}", headers=api_headers(), json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def ensure_catalog():
    if "catalog" not in st.session_state:
        data = api_get("/catalog/vehicles")
        st.session_state.catalog = {c["code"]: c for c in data.get("cards", [])}

# -------------------------
# Session init
# -------------------------

if "token" not in st.session_state:
    st.session_state.token = None
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

# -------------------------
# Sidebar: Auth
# -------------------------

with st.sidebar:
    st.header("Account")

    if not st.session_state.token:
        tab1, tab2 = st.tabs(["Login", "Registrieren"])

        with tab1:
            u = st.text_input("Username", key="login_u")
            p = st.text_input("Passwort", type="password", key="login_p")
            if st.button("Login"):
                try:
                    data = requests.post(
                        f"{API_BASE}/auth/login",
                        json={"username": u, "password": p},
                        timeout=20
                    ).json()
                    if "token" not in data:
                        st.error(data)
                    else:
                        st.session_state.token = data["token"]
                        st.success("Eingeloggt.")
                        st.rerun()
                except Exception as e:
                    st.error(str(e))

        with tab2:
            u2 = st.text_input("Username", key="reg_u")
            p2 = st.text_input("Passwort", type="password", key="reg_p")
            if st.button("Account erstellen"):
                try:
                    r = requests.post(
                        f"{API_BASE}/auth/register",
                        json={"username": u2, "password": p2},
                        timeout=20
                    )
                    if r.status_code >= 400:
                        st.error(r.text)
                    else:
                        st.success("Registriert. Bitte einloggen.")
                except Exception as e:
                    st.error(str(e))
    else:
        try:
            me = api_get("/me")
            st.write(f"Angemeldet als: **{me['username']}**")
            st.write(f"Coins: **{me['coins']}**")
        except Exception as e:
            st.error(f"Backend nicht erreichbar: {e}")

        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.room_code = ""
            if "catalog" in st.session_state:
                del st.session_state.catalog
            st.rerun()

if not st.session_state.token:
    st.info("Bitte zuerst einloggen/registrieren.")
    st.stop()

ensure_catalog()

# -------------------------
# Main Tabs
# -------------------------

t_collection, t_deck, t_boosters, t_rooms, t_match = st.tabs(
    ["Sammlung", "Deck", "Booster", "Räume", "Duell"]
)

# -------------------------
# Sammlung
# -------------------------

with t_collection:
    st.subheader("Ihre Sammlung")
    data = api_get("/collection")
    cards = data.get("cards", [])

    if not cards:
        st.caption("Noch keine Karten. Kaufen Sie Booster.")
    else:
        # grouped by theme
        by_theme = {}
        for c in cards:
            by_theme.setdefault(c["theme"], []).append(c)

        for theme in ["feuer", "rd", "thl"]:
            if theme in by_theme:
                st.markdown(f"### {theme.upper()}")
                for c in sorted(by_theme[theme], key=lambda x: (x["rarity"], x["name"])):
                    st.write(f"{c['qty']}× {c['name']} ({c['code']}) – {c['rarity']}")

# -------------------------
# Deckbuilding
# -------------------------

with t_deck:
    st.subheader("Deck erstellen (exakt 40 Karten)")

    deck = api_get("/deck/get")
    st.write(f"Aktuelles Deck: **{deck['name']}**")
    current = deck.get("cards", {})

    data = api_get("/collection")
    cards = data.get("cards", [])
    if not cards:
        st.info("Sie brauchen zuerst Karten (Booster), um ein Deck zu bauen.")
        st.stop()

    # UI: only owned cards
    st.caption("Regel: Deckgröße muss exakt 40 sein. Maximal pro Karte: Besitzmenge.")
    new_cards = {}
    total = 0

    # Sort: theme then rarity then name
    def sort_key(c):
        return (c["theme"], c["rarity"], c["name"])

    for c in sorted(cards, key=sort_key):
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
        try:
            api_post("/deck/save", {"name": "Standard", "cards": new_cards})
            st.success("Deck gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

# -------------------------
# Booster
# -------------------------

with t_boosters:
    st.subheader("Booster kaufen & öffnen")
    col1, col2, col3 = st.columns(3)

    def buy(theme: str):
        res = api_post("/booster/buy_open", {"theme": theme})
        st.success(f"Booster '{theme}' geöffnet. Coins jetzt: {res['coins']}")
        st.write("Gezogene Karten:")
        for c in res["cards"]:
            st.write(f"- {c['name']} ({c['code']}) – {c['rarity']}")

    with col1:
        st.markdown("### Feuer-Booster")
        st.caption("Mehr Feuerwehr-Fahrzeuge (Brand/Höhe/Gefahrgut).")
        if st.button("Feuer-Booster kaufen (25 Coins)"):
            buy("feuer")

    with col2:
        st.markdown("### Rettungsdienst-Booster")
        st.caption("Mehr RD-Fahrzeuge (rettung/koord).")
        if st.button("RD-Booster kaufen (25 Coins)"):
            buy("rd")

    with col3:
        st.markdown("### THL-Booster")
        st.caption("Mehr THL-Fahrzeuge (technik/koord).")
        if st.button("THL-Booster kaufen (25 Coins)"):
            buy("thl")

# -------------------------
# Räume
# -------------------------

with t_rooms:
    st.subheader("Duellräume")

    r1, r2 = st.columns(2)

    with r1:
        st.markdown("### Raum erstellen")
        custom = st.text_input("Optionaler Raumcode (z. B. BERLIN1)", value="")
        if st.button("Erstellen"):
            try:
                res = api_post("/room/create", {"room_code": custom or None})
                st.session_state.room_code = res["room_code"]
                st.success(f"Raum erstellt: {res['room_code']}")
            except Exception as e:
                st.error(str(e))

    with r2:
        st.markdown("### Raum beitreten")
        join_code = st.text_input("Raumcode", value=st.session_state.room_code)
        if st.button("Beitreten"):
            try:
                res = api_post("/room/join", {"room_code": join_code})
                st.session_state.room_code = res["room_code"]
                st.success(f"Beigetreten: {res['room_code']}")
            except Exception as e:
                st.error(str(e))

    if st.session_state.room_code:
        st.divider()
        status = api_get("/room/status", params={"room_code": st.session_state.room_code})
        st.write(f"Aktueller Raum: **{status['room_code']}**")
        st.write("Spieler im Raum:")
        for p in status["players"]:
            st.write(f"- {p['username']} (id={p['id']})")

        st.caption("Hinweis: Match starten klappt nur, wenn 2 Spieler im Raum sind und beide ein 40er Deck gespeichert haben.")
        if st.button("Match starten"):
            try:
                api_post("/match/start", {"room_code": st.session_state.room_code})
                st.success("Match gestartet.")
            except Exception as e:
                st.error(str(e))

# -------------------------
# Duell
# -------------------------

with t_match:
    st.subheader("Duell (Turn-based MVP)")
    if not st.session_state.room_code:
        st.info("Bitte zuerst einen Raum erstellen/beitreten.")
        st.stop()

    me = api_get("/me")
    my_id = int(me["user_id"])

    try:
        state = api_get("/match/state", params={"room_code": st.session_state.room_code})
    except Exception as e:
        st.error(f"Match nicht verfügbar. Starten Sie zuerst ein Match im Raum. Details: {e}")
        st.stop()

    st.write(f"Runde: {state['round_no']} | Phase: **{state['phase']}** | Druck: {state['pressure']}/{state['pressure_max']}")
    st.write(f"Aktiver Spieler (user_id): **{state['active_player']}**")

    my = state["players"].get(str(my_id))
    if not my:
        st.error("Sie sind nicht Teil dieses Matches.")
        st.stop()

    st.write(f"Ihre Ressourcen: EP={my['ep']} | Crew={my['crew']} | EW={my['ew']} | Deck (Draw-Pile)={len(my.get('draw_pile', []))}")
    st.divider()

    # incidents
    cols = st.columns(2)
    for i in [0, 1]:
        with cols[i]:
            inc = state["open_incidents"][i]
            st.markdown(f"### Slot {i+1}: {inc['name']}")
            st.write(f"Zeit: {inc['time_left']} | EW: {inc['ew']}")
            st.write("Anforderungen:")
            st.json({k: v for k, v in inc["req"].items() if int(v) > 0})

    st.divider()

    # Hand display with readable names
    st.markdown("## Ihre Hand (Fahrzeuge)")
    if not my["hand"]:
        st.caption("Keine Karten auf der Hand.")
    else:
        options = []
        for code in my["hand"]:
            meta = st.session_state.catalog.get(code)
            if meta:
                s = f"{meta['name']} ({code}) – EP {meta['cost_ep']} | Crew {meta['crew']} | Stats {meta['stats']}"
            else:
                s = f"{code}"
            options.append((code, s))

        label_map = {s: code for code, s in options}
        selected_label = st.selectbox("Karte wählen", [s for _, s in options])
        selected_code = label_map[selected_label]

        slot = st.radio("Slot", [0, 1], horizontal=True)

        if st.button("Zuweisen (nur Planung & wenn Sie dran sind)"):
            try:
                api_post("/match/assign", {"room_code": st.session_state.room_code, "slot": slot, "card_code": selected_code})
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

    with st.expander("Log (letzte 50)"):
        for line in state.get("log", [])[-50:]:
            st.write(line)
