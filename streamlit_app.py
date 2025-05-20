# streamlit_app.py – CATPrep × MacroTracker 𝘷2
"""
Duolingo‑inspired upgrade (Sprint 1 scope)
=========================================
Implemented features:
1. **Sticky XP/Streak ribbon** – appears on every page.
2. **User‑selectable daily study goal** – Light (45 min) · Regular (60 min) · Intense (90 min).
3. **Goal progress ring** – linear `st.progress` bar that fills as minutes are logged.
4. **Lottie celebration** when the ring hits 100 %.

Offline‑friendly: works without Supabase; persists within the session only.  
(Provide Supabase keys in *Secrets* for cross‑device sync.)
"""
from __future__ import annotations
from datetime import date, timedelta
import json
import time
import streamlit as st
import pandas as pd

# Optional Supabase import
try:
    from supabase import create_client, Client  # type: ignore
except ModuleNotFoundError:
    Client = None  # type: ignore

# Lottie helper (minimal, no external lib needed)
@st.cache_data(show_spinner=False)
def load_lottie_confetti() -> dict:
    # Public-domain confetti JSON hosted on GitHub gist
    import requests, os
    url = "https://raw.githubusercontent.com/iamnotstatic/lottie-files/main/confetti.json"
    r = requests.get(url, timeout=5)
    return r.json() if r.status_code == 200 else {}

# ──────────────────── Constants ────────────────────
SECTIONS = ("VARC", "DILR", "QA")
GOALS = {"Light": 45, "Regular": 60, "Intense": 90}  # minutes
XP_PER_MIN = 1
MEAL_BONUS = 5

# ──────────────────── Supabase (optional) ──────────
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client | None:
    url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_KEY")
    if url and key and Client:
        return create_client(url, key)
    return None

supabase = get_supabase()

# ──────────────────── Session init ─────────────────

def init_state():
    ss = st.session_state
    ss.setdefault("profile", None)
    ss.setdefault("study_log", [])  # [{date, minutes}]
    ss.setdefault("meal_log", [])
    ss.setdefault("goal_minutes", GOALS["Regular"])  # default 60
    ss.setdefault("celebrated", False)

init_state()

# ──────────────────── Helper fns ───────────────────

def today() -> date:
    return date.today()


def today_section() -> str:
    return SECTIONS[today().toordinal() % len(SECTIONS)]


def minutes_logged_today() -> int:
    return sum(entry["minutes"] for entry in st.session_state.study_log if entry["date"] == today())

# ──────────────────── Onboarding ───────────────────

def onboarding():
    st.title("🎯 Welcome – Set your goals")
    with st.form("onboard"):
        name = st.text_input("Your name")
        goal_choice = st.radio("Choose your daily study goal", list(GOALS.keys()))
        exam_date = st.date_input("CAT exam date", value=date(date.today().year, 11, 24))
        target = st.slider("Target percentile", 70, 100, 99)
        macro_goal = st.selectbox("Gym nutrition goal", ("Cut", "Bulk", "Maintain"))
        if st.form_submit_button("Save & Start"):
            profile = {
                "name": name,
                "exam_date": exam_date.isoformat(),
                "target_percentile": target,
                "macro_goal": macro_goal,
                "streak": 0,
                "xp": 0,
                "last_active": today().isoformat(),
            }
            st.session_state.profile = profile
            st.session_state.goal_minutes = GOALS[goal_choice]
            st.experimental_rerun()

# ──────────────────── Gamification ────────────────

def award_xp(amount: int):
    st.session_state.profile["xp"] += amount


def bump_streak_if_first_action_today():
    prof = st.session_state.profile
    if prof["last_active"] == today().isoformat():
        return
    prof["streak"] += 1
    prof["last_active"] = today().isoformat()

# ──────────────────── Sticky ribbon ───────────────

def sticky_ribbon():
    prof = st.session_state.profile
    with st.container():
        col1, col2 = st.columns(2)
        col1.markdown(f"### 🔥 Streak: {prof['streak']}")
        col2.markdown(f"### ⭐ XP: {prof['xp']}")
        st.markdown("---")

# ──────────────────── Pages ───────────────────────

def page_home():
    sticky_ribbon()
    prof = st.session_state.profile
    st.header("Dashboard")
    # Goal progress
    logged = minutes_logged_today()
    pct = min(int(logged / st.session_state.goal_minutes * 100), 100)
    st.subheader(f"Study Progress: {logged}/{st.session_state.goal_minutes} min ({pct} %)")
    st.progress(pct / 100)

    # Celebrate on first 100 % completion per day
    if pct == 100 and not st.session_state.celebrated:
        st.success("Goal met – great job! 🎉")
        try:
            from streamlit_lottie import st_lottie  # type: ignore
            st_lottie(load_lottie_confetti(), height=300, loop=False)
        except (ModuleNotFoundError, ValueError):
            st.balloons()
        st.session_state.celebrated = True

    st.info(f"Today’s focus: **{today_section()}**")


def page_study():
    sticky_ribbon()
    st.header("📚 Log Study Time")
    mins = st.number_input("Minutes just studied", 0, 180, step=5)
    if st.button("Save study") and mins > 0:
        st.session_state.study_log.append({"date": today(), "minutes": int(mins)})
        award_xp(mins * XP_PER_MIN)
        bump_streak_if_first_action_today()
        st.success("Logged & XP awarded!")
        st.experimental_rerun()


def page_meals():
    sticky_ribbon()
    st.header("🍽️ Meal Logger")
    cols = st.columns(5)
    item = cols[0].text_input("Item")
    cal = cols[1].number_input("Cal", 0)
    protein = cols[2].number_input("Protein", 0)
    carbs = cols[3].number_input("Carbs", 0)
    fat = cols[4].number_input("Fat", 0)
    if st.button("Add meal") and item:
        st.session_state.meal_log.append({
            "date": today(), "item": item, "cal": int(cal), "protein": int(protein), "carbs": int(carbs), "fat": int(fat)
        })
        award_xp(MEAL_BONUS)
        bump_streak_if_first_action_today()
        st.toast("Meal saved 🍏")
        st.experimental_rerun()


def page_dashboard():
    sticky_ribbon()
    st.header("📊 Study Minutes – Last 7 Days")
    df = pd.DataFrame(st.session_state.study_log)
    if not df.empty:
        last7 = df[df["date"] >= today() - timedelta(days=6)]
        st.line_chart(last7, x="date", y="minutes")
    else:
        st.info("No study data yet.")

# ──────────────────── Router ─────────────────────
if st.session_state.profile is None:
    onboarding()
    st.stop()

st.sidebar.title("Navigate")
choice = st.sidebar.radio("", ("Home", "Study", "Meals", "Stats"))

if choice == "Home":
    page_home()
elif choice == "Study":
    page_study()
elif choice == "Meals":
    page_meals()
else:
    page_dashboard()
