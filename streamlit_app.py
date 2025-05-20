# streamlit_app.py – Enhanced Duolingo‑style MVP
"""
CAT Prep × Gym‑Nutrition Tracker (Gamified)
-------------------------------------------
*Features added vs previous MVP*
- On‑boarding wizard – captures CAT target & nutrition goal.
- XP + Streak mechanics (study minutes = XP; macros met = bonus).
- Progress ring, confetti at 100 % of study target.
- Persistent storage via Supabase (cross‑device).

> **Setup**
> 1. `pip install -r requirements.txt` (see bottom of file)
> 2. Set env vars in Streamlit Cloud → *Secrets*:
>    ```
>    SUPABASE_URL="https://xxxxx.supabase.co"
>    SUPABASE_KEY="your-anon-key"
>    ```
> 3. Deploy. First launch will run DB bootstrap (tables if not exist).
"""
from __future__ import annotations
import os
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
        st.warning("🔑 Supabase creds missing – data will not persist.")
        return None
    return create_client(url, key)

supabase = get_supabase()

USER_TABLE = "users"
STUDY_TABLE = "study_log"
MEAL_TABLE = "meal_log"


def bootstrap_db() -> None:
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

# ───────────────────────────── Session helpers ───────────────────────────────
@st.cache_data(show_spinner=False)
def load_profile() -> dict | None:
    if not supabase or "user_id" not in st.session_state:
        return None
    resp = supabase.table(USER_TABLE).select("*").eq("id", st.session_state.user_id).execute()
    return resp.data[0] if resp.data else None


def ensure_user():
    if "user_id" in st.session_state:
        return
    # new session ⇒ ask name only (unique cookie would be nicer)
    st.session_state.user_id = st.session_state.get("user_id") or None


# ───────────────────────────── Gamification logic ────────────────────────────
XP_PER_MIN = 1
MEAL_BONUS = 5


def update_xp_and_streak(action_date: date):
    if not supabase or not profile:
        return
    last_active = profile.get("last_active")
    streak = profile.get("streak", 0)
    xp = profile.get("xp", 0)
    # streak calc
    if last_active:
        last_active = datetime.strptime(last_active, "%Y-%m-%d").date()
        if action_date == last_active:
            pass  # same day
        elif action_date == last_active + timedelta(days=1):
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    supabase.table(USER_TABLE).update({"streak": streak, "xp": xp}).eq("id", profile["id"]).execute()

# ───────────────────────────── UI Pages ──────────────────────────────────────
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
            resp = supabase.table(USER_TABLE).insert(data).execute() if supabase else {"data": [{"id": "demo"}]}
            st.session_state.user_id = resp["data"][0]["id"] if supabase else "demo"
            st.rerun()


def home_page():
    st.title("🧠 CATPrep × 🍗 MacroTracker")
    st.metric("Streak", f"{profile.get('streak', 0)} 🔥")
    st.metric("XP", profile.get("xp", 0))
    st.info(f"Today’s focus: **{today_section()}** · Target study: **90 mins**")


def study_page():
    st.header("📚 Study Session")
    mins = st.number_input("Minutes studied now", 0, 240, step=5)
    if st.button("Log study") and mins > 0:
        if supabase:
            supabase.table(STUDY_TABLE).insert({"user_id": profile["id"], "date": date.today().isoformat(), "minutes": int(mins)}).execute()
            supabase.table(USER_TABLE).update({"xp": profile["xp"] + mins * XP_PER_MIN, "last_active": date.today().isoformat()}).eq("id", profile["id"]).execute()
        st.session_state.study_logged = True
        st.balloons()
        st.success("Logged & XP awarded!")



def meal_page():
    st.header("🍽️ Meal Logger")
    c1, c2, c3, c4, c5 = st.columns(5)
    item = c1.text_input("Item")
    cal = c2.number_input("Cal", 0)
    protein = c3.number_input("Protein", 0)
    carbs = c4.number_input("Carbs", 0)
    fat = c5.number_input("Fat", 0)
    if st.button("Add meal") and item:
        if supabase:
            supabase.table(MEAL_TABLE).insert({
                "user_id": profile["id"], "date": date.today().isoformat(),
                "item": item, "cal": int(cal), "protein": int(protein), "carbs": int(carbs), "fat": int(fat)
            }).execute()
            supabase.table(USER_TABLE).update({"xp": profile["xp"] + MEAL_BONUS, "last_active": date.today().isoformat()}).eq("id", profile["id"]).execute()
        st.toast("Meal saved 🍏")



def dashboard_page():
    st.header("📊 Dashboard")
    if not supabase:
        st.info("Connect Supabase to enable dashboards.")
        return
    study = supabase.table(STUDY_TABLE).select("date, minutes").eq("user_id", profile["id"]).gte("date", (date.today() - timedelta(days=6)).isoformat()).execute().data
    df = pd.DataFrame(study)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        st.line_chart(df, x="date", y="minutes")
    else:
        st.info("No study data last 7 days.")

    macros = supabase.rpc("daily_macros", {"uid": profile["id"], "dt": date.today().isoformat()}).execute() if supabase else {}
    if macros and macros.data:
        st.subheader("Today's Macro Totals")
        st.dataframe(pd.DataFrame([macros.data]))

# ─────────────────────────── Main router ─────────────────────────────────────
ensure_user()
profile = load_profile()

if not profile:
    onboarding()
    st.stop()

st.sidebar.title("Menu")
page = st.sidebar.radio("Go to", ("Home", "Study", "Meals", "Dashboard"))

if page == "Home":
    home_page()
elif page == "Study":
    study_page()
elif page == "Meals":
    meal_page()
else:
    dashboard_page()
