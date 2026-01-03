import streamlit as st
from game.models import Player
from game.engine import start_game, play_vehicle

st.set_page_config(page_title="Einsatzleitung Berlin – Prototyp")

if "player" not in st.session_state:
    st.session_state.player = Player(name="Spieler 1")
    start_game(st.session_state.player)

player = st.session_state.player

st.title("🚒 Einsatzleitung Berlin – Prototyp")

st.subheader("Ressourcen")
st.write(f"EP: {player.ep} | Personal: {player.crew}")

st.subheader("Handkarten")
for card in player.hand:
    if st.button(f"{card.name} (EP {card.cost_ep})", key=card.id):
        msg = play_vehicle(player, card.id)
        st.success(msg)
        st.experimental_rerun()
