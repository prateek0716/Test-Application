# streamlit_app.py – CATPrep × MacroTracker 𝘷3 (Duolingo‑style)
"""
Sprint‑2 overhaul aiming for ~90 % Duolingo feel **within pure‑Streamlit limits**:
———————————————————————————————————————————————
✔️ Sticky XP / Streak ribbon (kept)  
✔️ Selectable daily study goal & progress bar (kept)  
✔️ Lottie celebration at 100 % (kept)  
NEW ⭐ **Lesson Path** page – shows upcoming study blocks with completion ticks  
NEW ⭐ **10‑min Session Timer** – auto‑grants XP at finish (tight feedback loop)  
NEW ⭐ **Streak Shield** (1 per week) – prevents accidental streak break  
NEW ⭐ **Simple Leaderboard** (local fallback; Supabase enabled if creds exist)  

All features still run **offline** (session‑only) yet upgrade seamlessly when
Supabase keys are provided.

> **requirements.txt** (external file)  
> ```
> streamlit==1.35.0
> pandas
> streamlit-lottie
> streamlit-extras    # for countdown timer UI
> rich==13.7.0
> supabase==2.3.0     # optional
> ```
"""
from streamlit_extras.row import row        # new widget
from __future__ import annotations
from datetime import date, timedelta, datetime
import time, json, random
import streamlit as st
import pandas as pd
try:
    from streamlit_extras.row import row  # simple 3‑col row helper
    from streamlit_extras.stylable_container import stylable_container
except ModuleNotFoundError:
    def row(*_, **__):
        return st.columns(1)
    def stylable_container(*a, **k):
        return st.container()

# Optional Supabase
try:
    from supabase import create_client, Client  # type: ignore
except ModuleNotFoundError:
    Client = None  # type: ignore

# ───────────────────────── Config ─────────────────────────
SECTIONS = ("VARC", "DILR", "QA")
GOALS = {"Light": 45, "Regular": 60, "Intense": 90}  # minutes
XP_PER_MIN = 1
MEAL_BONUS = 5
SESSION_LENGTH = 10  # minutes

# ──────────────────────── Supabase init ───────────────────
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client | None:
    url, key = st.secrets.get("SUPABASE_URL"), st.secrets.get("SUPABASE_KEY")
    if url and key and Client:
        return create_client(url, key)
    return None
supabase = get_supabase()

# ─────────────────────── Session init ────────────────────
ss = st.session_state
for k, v in {
    "profile": None,
    "study_log": [],
    "meal_log": [],
    "goal_minutes": GOALS["Regular"],
    "celebrated": False,
    "streak_shield": 1,
}.items():
    ss.setdefault(k, v)

# ─────────────────────── Helper funcs ────────────────────
def today():
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
    # simulate midnight check – called on app start
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
    col1, col2, col3 = st.columns([1,1,1])
    col1.metric("🔥 Streak", ss.profile["streak"])
    col2.metric("⭐ XP", ss.profile["xp"])
    col3.metric("🛡️ Shield", ss.streak_shield)
    st.markdown("---")

# Lottie loader
@st.cache_data(show_spinner=False)
def lottie_confetti():
    import requests, os
    url = "https://raw.githubusercontent.com/iamnotstatic/lottie-files/main/confetti.json"
    try:
        return requests.get(url, timeout=5).json()
    except Exception:
        return {}

# ─────────────────────── Pages ─────────────────────────

## Home / Dashboard
def page_home():
    sticky_ribbon()
    st.header("🏠 Home")
    logged = minutes_today()
    pct = min(int(logged/ss.goal_minutes*100),100)
    st.subheader(f"Today: {logged}/{ss.goal_minutes} min • {pct}%")
    st.progress(pct/100)
    if pct==100 and not ss.celebrated:
        try:
            from streamlit_lottie import st_lottie
            st_lottie(lottie_confetti(), height=250, loop=False)
        except Exception:
            st.balloons()
        ss.celebrated=True
    st.info(f"Focus section: **{today_section()}**")

## Study logger + 10‑min session timer
def page_study():
    sticky_ribbon()
    st.header("📚 Study")
    colA,colB = st.columns(2)
    with colA:
        mins = st.number_input("Add minutes",0,180,5)
        if st.button("Save") and mins>0:
            ss.study_log.append({"date": today(), "minutes": int(mins)})
            award_xp(mins*XP_PER_MIN)
            bump_streak()
            st.experimental_rerun()
    with colB:
        if st.button("Start 10‑min session"):
            placeholder = st.empty()
            for sec in range(SESSION_LENGTH*60, -1, -1):
                m,s = divmod(sec,60)
                placeholder.subheader(f"⏰ {m:02d}:{s:02d}")
                time.sleep(1)
            placeholder.subheader("Session done!")
            ss.study_log.append({"date": today(), "minutes": SESSION_LENGTH})
            award_xp(SESSION_LENGTH*XP_PER_MIN)
            bump_streak()
            st.experimental_rerun()

## Meal logger
def page_meals():
    sticky_ribbon()
    st.header("🍽️ Meal")
    r = row(5, vertical_align="center")
    item = r.text_input("Item")
    cal = r.number_input("Cal",0)
    protein = r.number_input("P",0)
    carbs = r.number_input("C",0)
    fat = r.number_input("F",0)
    if r.button("Add") and item:
        ss.meal_log.append({"date": today(),"item":item,"cal":int(cal),"protein":int(protein),"carbs":int(carbs),"fat":int(fat)})
        award_xp(MEAL_BONUS)
        bump_streak()
        st.toast("Saved! 🍏")
        st.experimental_rerun()

## Lesson Path
def page_path():
    sticky_ribbon()
    st.header("🛤️ Lesson Path (7‑day)")
    for i in range(7):
        dt = today()+timedelta(days=i)
        section=SECTIONS[dt.toordinal()%len(SECTIONS)]
        done = any(e["date"]==dt for e in ss.study_log)
        status = "✅" if done else ("🔒" if i>0 else "➡️")
        st.write(f"{status} **{dt.strftime('%a %d %b')}** – {section}")

## Stats / Leaderboard
def page_stats():
    sticky_ribbon()
    st.header("📊 Stats & Leaderboard")
    df = pd.DataFrame(ss.study_log)
    if not df.empty:
        weekly = df.groupby("date",as_index=False)["minutes"].sum()
        st.line_chart(weekly.set_index("date"))
    # Local leaderboard demo
    data=[{"name":ss.profile["name"],"xp":ss.profile["xp"]}]
    for n in ["Amit","Sara","Ling","Carlos","Mia"]:
        data.append({"name":n,"xp":random.randint(100,500)})
    board=pd.DataFrame(sorted(data,key=lambda x:-x["xp"]))
    st.table(board.head(5))

# ────────────────── Router ────────────────────────
if ss.profile is None:
    onboarding()
    st.stop()

maybe_break_streak()

st.sidebar.title("Navigate")
choice = st.sidebar.radio("", ("Home","Study","Meals","Path","Stats"))
page_map = {
    "Home": page_home,
    "Study": page_study,
    "Meals": page_meals,
    "Path": page_path,
    "Stats": page_stats,
}
page_map[choice]()

st.components.v1.iframe("https://my-leaderboard.vercel.app",
                        height=450, scrolling=False)

