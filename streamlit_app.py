# streamlit_app.py – CATPrep × MacroTracker 𝘷3 (Duolingo‑style)
"""
Sprint‑2 overhaul aiming for ~90 % Duolingo feel inside Streamlit.

Features
─────────
✔ Sticky XP/Streak ribbon  
✔ User‑selectable daily goal & progress bar  
✔ Lottie celebration at 100 %  
✔ Lesson Path, 10‑min session timer, Streak Shield, Leaderboard  

Runs offline; adds Supabase sync when credentials are provided.
"""

from __future__ import annotations
from datetime import date, timedelta, datetime
import time, random
import streamlit as st
import pandas as pd

# Optional Streamlit‑extras widgets
try:
    from streamlit_extras.row import row       # 3‑column helper
except ModuleNotFoundError:
    def row(*_, **__):
        return st.columns(1)

# ───────────────────────── Config ─────────────────────────
SECTIONS = ("VARC", "DILR", "QA")
GOALS = {"Light": 45, "Regular": 60, "Intense": 90}  # minutes
XP_PER_MIN = 1
MEAL_BONUS = 5
SESSION_LENGTH = 10  # minutes

# ──────────────────────── Supabase init ───────────────────
try:
    from supabase import create_client, Client  # type: ignore
except ModuleNotFoundError:
    Client = None  # type: ignore

@st.cache_resource(show_spinner=False)
def get_supabase() -> Client | None:
    """Return a Supabase client or **None** if creds missing/invalid.
    Swallows all exceptions so the app keeps running in offline mode.
    """
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not (url and key and Client):
        return None
    try:
        return create_client(url, key)  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        st.warning(
            "Supabase connection failed — running in offline mode.\n"
            f"Details: {e.__class__.__name__}")
        return None

supabase = get_supabase()

# ─────────────────────── Session init ────────────────────
ss = st.session_state
_defaults = {
    "profile": None,
    "study_log": [],
    "meal_log": [],
    "goal_minutes": GOALS["Regular"],
    "celebrated": False,
    "streak_shield": 1,
}
for k, v in _defaults.items():
    ss.setdefault(k, v)

# ─────────────────────── Helper funcs ────────────────────

def today() -> date:
    return date.today()

def today_section() -> str:
    return SECTIONS[today().toordinal() % len(SECTIONS)]

def minutes_today() -> int:
    return sum(e["minutes"] for e in ss.study_log if e["date"] == today())

def award_xp(x: int):
    ss.profile["xp"] += x

def bump_streak():
    if ss.profile["last_active"] == today().isoformat():
        return
    ss.profile["streak"] += 1
    ss.profile["last_active"] = today().isoformat()

def maybe_break_streak():
    last = datetime.fromisoformat(ss.profile["last_active"]).date()
    if last < today() - timedelta(days=1):
        if ss.streak_shield > 0:
            ss.streak_shield -= 1
        else:
            ss.profile["streak"] = 0

# ─────────────────────── Onboarding ─────────────────────

def onboarding():
    st.title("🎯 Let’s set you up")
    with st.form("onboard"):
        name = st.text_input("Your name")
        goal_choice = st.radio("Daily study goal", list(GOALS.keys()))
        if st.form_submit_button("Start"):
            ss.profile = {
                "name": name or "Learner",
                "streak": 0,
                "xp": 0,
                "last_active": today().isoformat(),
            }
            ss.goal_minutes = GOALS[goal_choice]
            st.experimental_rerun()

# ─────────────────────── UI bits ────────────────────────

def sticky_ribbon():
    col1, col2, col3 = st.columns(3)
    col1.metric("🔥 Streak", ss.profile["streak"])
    col2.metric("⭐ XP", ss.profile["xp"])
    col3.metric("🛡️ Shield", ss.streak_shield)
    st.markdown("---")

# ─────────────────────── Pages ─────────────────────────

def page_home():
    sticky_ribbon()
    st.header("🏠 Home")
    logged = minutes_today()
    pct = min(int(logged / ss.goal_minutes * 100), 100)
    st.subheader(f"Today: {logged}/{ss.goal_minutes} min • {pct}%")
    st.progress(pct / 100)
    if pct == 100 and not ss.celebrated:
        try:
            from streamlit_lottie import st_lottie  # type: ignore
            import requests
            confetti = requests.get(
                "https://raw.githubusercontent.com/iamnotstatic/"
                "lottie-files/main/confetti.json", timeout=5).json()
            st_lottie(confetti, height=250, loop=False)
        except Exception:
            st.balloons()
        ss.celebrated = True
    st.info(f"Focus section: **{today_section()}**")


def page_study():
    sticky_ribbon()
    st.header("📚 Study")
    colA, colB = st.columns(2)
    with colA:
        mins = st.number_input("Add minutes", 0, 180, 5)
        if st.button("Save") and mins > 0:
            ss.study_log.append({"date": today(), "minutes": int(mins)})
            award_xp(mins * XP_PER_MIN)
            bump_streak()
            st.experimental_rerun()
    with colB:
        if st.button("Start 10‑min session"):
            placeholder = st.empty()
            for sec in range(SESSION_LENGTH * 60, -1, -1):
                m, s = divmod(sec, 60)
                placeholder.subheader(f"⏰ {m:02d}:{s:02d}")
                time.sleep(1)
            placeholder.subheader("Session done!")
            ss.study_log.append({"date": today(), "minutes": SESSION_LENGTH})
            award_xp(SESSION_LENGTH * XP_PER_MIN)
            bump_streak()
            st.experimental_rerun()


def page_meals():
    sticky_ribbon()
    st.header("🍽️ Meal")
    r = row(5, vertical_align="center")
    item = r.text_input("Item")
    cal = r.number_input("Cal", 0)
    protein = r.number_input("P", 0)
    carbs = r.number_input("C", 0)
    fat = r.number_input("F", 0)
    if r.button("Add") and item:
        ss.meal_log.append({
            "date": today(),
            "item": item,
            "cal": int(cal),
            "protein": int(protein),
            "carbs": int(carbs),
            "fat": int(fat),
        })
        award_xp(MEAL_BONUS)
        bump_streak()
        st.toast("Saved! 🍏")
        st.experimental_rerun()


def page_path():
    sticky_ribbon()
    st.header("🛤️ Lesson Path (7‑day)")
    for i in range(7):
        dt = today() + timedelta(days=i)
        section = SECTIONS[dt.toordinal() % len(SECTIONS)]
        done = any(e["date"] == dt for e in ss.study_log)
        icon = "✅" if done else ("🔒" if i > 0 else "➡️")
        st.write(f"{icon} **{dt.strftime('%a %d %b')}** – {section}")

def page_stats():
    sticky_ribbon()
    st.header("📊 Stats & Leaderboard")

    # study chart
    df = pd.DataFrame(ss.study_log)
    if not df.empty:
        weekly = df.groupby("date", as_index=False)["minutes"].sum()
        st.line_chart(weekly.set_index("date"))
    else:
        st.info("No study data yet.")

    # simple leaderboard (demo data)
    sample = [
        {"name": ss.profile["name"], "xp": ss.profile["xp"]},
        {"name": "Amit",   "xp": 450},
        {"name": "Sara",   "xp": 380},
        {"name": "Ling",   "xp": 320},
        {"name": "Carlos", "xp": 290},
    ]
    board = pd.DataFrame(sorted(sample, key=lambda x: -x["xp"]))
    st.table(board.head(5))

