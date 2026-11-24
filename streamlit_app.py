import base64
import html
import io
import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

import scene
import sounds

DEVELOPER_NAME = "Y SRIRAM NAGESH"
LINKEDIN_URL = "https://www.linkedin.com/in/sriram-nagesh-yellaboena/"

st.set_page_config(page_title="FLIP IT – Leave It to Chance", page_icon="🪙",
                   layout="wide")

st.markdown("<style>[data-testid='stAudio']{height:0;overflow:hidden;opacity:0;margin:0}</style>",
            unsafe_allow_html=True)

FRAME_MS = 42      # about 24 frames per second
HOLD_MS = 3000     # the GIF holds its last frame (the result) for 3 seconds


# ---------- Animations (built once, then cached for every visitor) ----------
def _to_gif(frames, durations):
    pal = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for f in frames]
    buf = io.BytesIO()
    pal[0].save(buf, format="GIF", save_all=True, append_images=pal[1:],
                duration=durations, disposal=1)      # no loop = plays once
    return buf.getvalue()



RELEASE_FRAME = int(scene.T_RELEASE * (scene.INTRO_FRAMES - 1))

@st.cache_resource(show_spinner="Rendering the cinematic scene (first visit only, please wait)...")
def build_animations():
    SOUND_LEAD = 0.0     # raise to 0.3-0.6 if you hear sound BEFORE the animation starts
    intro = [scene.render_intro_frame(i) for i in range(scene.INTRO_FRAMES)]
    gifs, finals, track = {}, {}, b""
    for result in ("HEADS", "TAILS"):
        frames = list(intro)
        durations = [FRAME_MS] * len(intro)
        for k in range(scene.SLOWMO_FRAMES):
            frames.append(scene.render_slowmo_frame(k, result))
            durations.append(int(FRAME_MS * (1 + 1.5 * k / scene.SLOWMO_FRAMES)))
        reveal_s = sum(durations) / 1000             # when the result starts appearing
        for k in range(scene.REVEAL_FRAMES):
            frames.append(scene.render_reveal_frame(k, result))
            durations.append(FRAME_MS)
        play_seconds = sum(durations) / 1000
        durations[-1] = HOLD_MS
        gifs[result] = (_to_gif(frames, durations), play_seconds)
        finals[result] = scene.render_final_frame(result)
        if not track:                                # same timing for HEADS and TAILS
            track = sounds.build_track(RELEASE_FRAME * FRAME_MS / 1000,
                                       reveal_s, play_seconds, SOUND_LEAD)
    return {"gifs": gifs, "finals": finals, "idle": intro[0], "track": track}


# ---------- Per-visitor state ----------
def init_state():
    ss = st.session_state
    ss.setdefault("history", [])
    ss.setdefault("next_id", 1)
    ss.setdefault("stats_from", 0)
    ss.setdefault("last", None)
    ss.setdefault("anim_on", True)
    ss.setdefault("confirm_clear", False)
    ss.setdefault("sound_on", True)


def counted():
    ss = st.session_state
    return [h for h in ss.history if h["id"] > ss.stats_from]


def get_stats():
    rows = counted()
    heads = sum(1 for r in rows if r["result"] == "HEADS")
    return len(rows), heads, len(rows) - heads


# ---------- The flip ----------
def show_stage(slot):
    anim = build_animations()
    last = st.session_state.last
    slot.image(anim["finals"][last] if last else anim["idle"], width=scene.W)


def run_flip(slot, choice1="", choice2=""):
    ss = st.session_state
    result = random.choice(["HEADS", "TAILS"])      # 1. decided BEFORE the animation
    anim = build_animations()

    if ss.anim_on:                                   # 2. the animation reveals it
        gif, seconds = anim["gifs"][result]
        b64 = base64.b64encode(gif).decode()
        nonce = random.random()                      # new page each flip, so the GIF restarts
        with slot:
            components.html(
                f'<body style="margin:0;background:#0A0A0C">'
                f'<img src="data:image/gif;base64,{b64}" '
                f'style="display:block;margin:auto;max-width:100%">'
                f'<!-- {nonce} --></body>',
                height=scene.H + 10)
        audio_slot = st.empty()
        if ss.sound_on:
            track = bytearray(anim["track"])
            track[44] = random.randrange(256)        # tiny change: browser treats it as a NEW sound
            audio_slot.audio(bytes(track), format="audio/wav", autoplay=True)
        time.sleep(seconds + 1.5)                    # wait for it to finish playing
        audio_slot.empty()
    slot.image(anim["finals"][result], width=scene.W)

    decision = ""
    if choice1 and choice2:
        decision = choice1 if result == "HEADS" else choice2
    now = datetime.now()
    ss.history.insert(0, {                           # 3. save only after it finished
        "id": ss.next_id, "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"), "result": result,
        "choice1": choice1, "choice2": choice2, "decision": decision})
    ss.next_id += 1
    ss.last = result
    return result, decision


def stat_cards():
    total, heads, tails = get_stats()
    hp = heads / total * 100 if total else 0
    tp = tails / total * 100 if total else 0
    cols = st.columns(5)
    for col, (label, value) in zip(cols, [
            ("Total flips", total), ("Heads", heads), ("Tails", tails),
            ("Heads %", f"{hp:.1f}%"), ("Tails %", f"{tp:.1f}%")]):
        col.metric(label, value)


# ---------- Pages ----------
def page_home():
    st.title("🪙 FLIP IT")
    st.caption("Leave It to Chance")
    slot = st.empty()
    show_stage(slot)
    if st.button("FLIP", type="primary", use_container_width=True, key="flip_home"):
        run_flip(slot)
    if st.session_state.last:
        st.markdown(f"### Last flip: {st.session_state.last}")
    stat_cards()          # drawn after the button, so it includes the new flip


def page_decision():
    st.title("Decision Mode")
    st.caption("HEADS picks Choice 1. TAILS picks Choice 2.")
    c1 = st.text_input("Choice 1 (HEADS)", placeholder="e.g. Watch a movie", max_chars=80)
    c2 = st.text_input("Choice 2 (TAILS)", placeholder="e.g. Play a game", max_chars=80)
    slot = st.empty()
    show_stage(slot)
    if st.button("FLIP", type="primary", use_container_width=True, key="flip_decision"):
        if not c1.strip() or not c2.strip():
            st.error("Please enter both choices first.")
        else:
            result, decision = run_flip(slot, c1.strip(), c2.strip())
            st.markdown(
                f"<h1 style='text-align:center;color:#D4AF37'>{html.escape(decision)}</h1>"
                f"<p style='text-align:center;color:#8A8A94'>The coin landed on {result}</p>",
                unsafe_allow_html=True)


def page_history():
    st.title("Flip History")
    ss = st.session_state
    if ss.history:
        cols = ["id", "date", "time", "result", "choice1", "choice2", "decision"]
        st.dataframe(pd.DataFrame(ss.history)[cols], use_container_width=True,
                     hide_index=True)
    else:
        st.info("No flips yet. Go flip a coin!")

    if ss.confirm_clear:
        st.warning("Delete ALL flip history? This cannot be undone.")
        a, b = st.columns(2)
        if a.button("Yes, delete everything"):
            ss.history, ss.stats_from, ss.confirm_clear = [], 0, False
            st.rerun()
        if b.button("Cancel"):
            ss.confirm_clear = False
            st.rerun()
    elif ss.history and st.button("Clear history"):
        ss.confirm_clear = True
        st.rerun()


def page_stats():
    st.title("Statistics")
    total, heads, tails = get_stats()
    stat_cards()
    df = pd.DataFrame({"Flips": [heads, tails]}, index=["Heads", "Tails"])
    st.bar_chart(df, color="#D4AF37")
    st.subheader("Recent activity")
    recent = counted()[:15]
    st.write("  ".join("🟡 H" if r["result"] == "HEADS" else "⚪ T" for r in recent)
             or "No flips yet.")
    st.caption("These percentages are historical observations only. Every flip is "
               "independent, so past results do not predict future outcomes.")


def page_settings():
    st.title("Settings")
    ss = st.session_state

    def toggle_sound():
        ss.sound_on = ss.sound_widget

    def toggle_anim():
        ss.anim_on = ss.anim_widget

    st.toggle("Sound effects", value=ss.sound_on, key="sound_widget",
              on_change=toggle_sound)
    st.toggle("Cinematic animation (off = instant result, no sound)", value=ss.anim_on,
              key="anim_widget", on_change=toggle_anim)
    st.divider()
    if st.button("Reset statistics (keeps history)"):
        ss.stats_from = ss.next_id - 1
        st.success("Statistics reset.")
    st.caption("FLIP IT web edition v1.0")


def page_about():
    st.title("About FLIP IT")
    st.write(
        "Built with Python, Streamlit and Pillow.\n\n"
        "Fair by design: every flip uses Python's random module, HEADS and TAILS "
        "are equally likely, and each flip is independent of all earlier flips. "
        "The result is decided before the animation starts; the animation only "
        "reveals it.")
    st.divider()
    st.caption("DEVELOPED BY")
    st.subheader(DEVELOPER_NAME)
    st.link_button("Connect on LinkedIn", LINKEDIN_URL)


# ---------- App ----------
init_state()
build_animations()        # first visit: renders the scene (shows a spinner)

st.sidebar.markdown("## 🪙 FLIP IT")
st.sidebar.caption("Leave It to Chance")
PAGES = {"Home": page_home, "Decision Mode": page_decision,
         "Flip History": page_history, "Statistics": page_stats,
         "Settings": page_settings, "About": page_about}
choice = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed")
PAGES[choice]()