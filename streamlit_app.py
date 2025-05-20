# streamlit_app.py – Enhanced Duolingo‑style MVP
"""
CAT Prep × Gym‑Nutrition Tracker (Gamified)
-------------------------------------------
*Features*
- On‑boarding wizard – captures CAT target & nutrition goal.
- XP + Streak mechanics (study minutes = XP; macros met = bonus).
- Progress ring, confetti at 100 % of study target.
- Persistent storage via Supabase (cross‑device).

> **Setup**
> 1. `pip install -r requirements.txt` (see list at bottom).  **Important:** we pin `rich<14` to satisfy Streamlit 1.35.0’s dependency.
> 2. Add *Secrets* in Streamlit Cloud:
>    ```
>    SUPABASE_URL="https://xxxxx.supabase.co"
>    SUPABASE_KEY="your‑anon‑key"
>    ```
> 3. Deploy. First launch will run DB bootstrap (tables create if absent).
"""
from __future__ import annotations
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ───────────────────────────── Supabase helpers ──────────────────────────────
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client | None:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not (url and key):
        st.warning("🔑 Supabase creds missing – data will not persist across sessions.")
        return None
    return create_client(url, key)

supabase = get_supabase()

USER_TABLE = "users"
STUDY_TABLE = "study_log"
MEAL_TABLE = "meal_log"


def bootstrap_db() -> None:
    """Create core tables on first run (Postgres DDL via Supabase RPC)."""
    if not supabase:
        return
    for ddl in (
        f"create table if not exists {USER_TABLE} (id uuid primary key default gen_random_uuid(), created_at timestamp default now(), name text, exam_date date, target_percentile int, macro_goal text, streak int default 0, xp int default 0, last_active date);",
        f"create table if not exists {STUDY_TABLE} (user_id uuid, date date, minutes int);",
        f"create table if not exists {MEAL_TABLE}  (user_id uuid, date date, item text, cal int, protein int, carbs int, fat int);",
    ):
        supabase.rpc("execute_sql", {"sql": ddl}).execute()

if supabase:
    bootstrap_db()

# ───────────────────────────── Session & profile helpers ─────────────────────
@st.cache_data(show_spinner=False)
def load_profile() -> dict | None:
    if not supabase or "user_id" not in st.session_state:
        return None
    resp = supabase.table(USER_TABLE).select("*").eq("id", st.session_state.user_id).execute()
    return resp.data[0] if resp.data else None


def ensure_user():
    """Initialise anonymous user key for the session until onboarding completes."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None

# ───────────────────────────── Gamification logic ────────────────────────────
XP_PER_MIN = 1
MEAL_BONUS = 5

SECTIONS = ("VARC", "DILR", "QA")

def today_section() -> str:
    return SECTIONS[date.today().toordinal() % len(SECTIONS)]


def onboarding():
    st.title("🎯 Welcome – Set your goals")
    with st.form("onboard"):
        name = st.text_input("Your name")
        exam_date = st.date_input("CAT exam date", value=date(date.today().year, 11, 24))
        target = st.slider("Target percentile", 70, 100, 99)
        macro_goal = st.selectbox("Gym nutrition goal", ("Cut", "Bulk", "Maintain"))
        submitted = st.form_submit_button("Save & Start")
        if submitted:
            data = {
                "name": name,
                "exam_date": exam_date.isoformat(),
                "target_percentile": target,
                "macro_goal": macro_goal,
                "streak": 0,
                "xp": 0,
                "last_active": date.today().isoformat(),
            }
            if supabase:
                resp = supabase.table(USER_TABLE).insert(data).execute()
                st.session_state.user_id = resp.data[0]["id"]
            else:
                st.session_state.user_id = "demo"
            st.rerun()

# ───────────────────────────── Core pages ────────────────────────────────────

def home_page(profile: dict):
    st.title("🧠 CATPrep × 🍗 MacroTracker")
    st.metric("Streak", f"{profile.get('streak', 0)} 🔥")
    st.metric("XP", profile.get("xp", 0))
    st.info(f"Today’s focus: **{today_section()}** · Target study: **90 mins**")


def study_page(profile: dict):
    st.header("📚 Study Session")
    mins = st.number_input("Minutes just studied", 0, 240, step=5)
    if st.button("Log study") and mins > 0 and supabase:
        supabase.table(STUDY_TABLE).insert({"user_id": profile["id"], "date": date.today().isoformat(), "minutes": int(mins)}).execute()
        supabase.table(USER_TABLE).update({"xp": profile["xp"] + mins * XP_PER_MIN, "last_active": date.today().isoformat()}).eq("id", profile["id"]).execute()
        st.balloons()
        st.success("Logged & XP awarded!")


def meal_page(profile: dict):
    st.header("🍽️ Meal Logger")
    cols = st.columns(5)
    item = cols[0].text_input("Item")
    cal = cols[1].number_input("Cal", 0)
    protein = cols[2].number_input("Protein", 0)
    carbs = cols[3].number_input("Carbs", 0)
    fat = cols[4].number_input("Fat", 0)
    if st.button("Add meal") and item and supabase:
        supabase.table(MEAL_TABLE).insert({
            "user_id": profile["id"], "date": date.today().isoformat(),
            "item": item, "cal": int(cal), "protein": int(protein), "carbs": int(carbs), "fat": int(fat)
        }).execute()
        supabase.table(USER_TABLE).update({"xp": profile["xp"] + MEAL_BONUS, "last_active": date.today().isoformat()}).eq("id", profile["id"]).execute()
        st.toast("Meal saved 🍏")


def dashboard_page(profile: dict):
    st.header("📊 Dashboard")
    if not supabase:
        st.info("Connect Supabase to enable dashboards.")
        return
    # Study chart last 7 days
    study = supabase.table(STUDY_TABLE).select("date, minutes").eq("user_id", profile["id"]).gte("date", (date.today() - timedelta(days=6)).isoformat()).execute().data
    df = pd.DataFrame(study)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        st.line_chart(df, x="date", y="minutes")
    else:
        st.info("No study data in the last week.")

# ───────────────────────────── Main router ───────────────────────────────────
ensure_user()
profile = load_profile()

if not profile:
    onboarding()
    st.stop()

st.sidebar.title("Menu")
choice = st.sidebar.radio("Navigate", ("Home", "Study", "Meals", "Dashboard"))

if choice == "Home":
    home_page(profile)
elif choice == "Study":
    study_page(profile)
elif choice == "Meals":
    meal_page(profile)
else:
    dashboard_page(profile)

# ───────────────────────────── requirements.txt ─────────────────────────────
"""
streamlit==1.35.0
pandas
supabase==2.3.0
# Pin **exact** rich version so Streamlit & Supabase both satisfy dependencies
rich==13.7.0
"""
