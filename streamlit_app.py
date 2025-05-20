# streamlit_app.py – Gamified CAT Prep × Nutrition Tracker
"""
Offline‑friendly Streamlit MVP that *optionally* syncs to Supabase.

🚀 **Deploy checklist**
1. **streamlit_app.py** → repo root (this file).
2. **requirements.txt** (separate file, *not* embedded in code) — copy/paste:
   ```
   streamlit==1.35.0
   pandas
   supabase==2.3.0   # optional; harmless if you don’t add keys
   rich==13.7.0       # pin required, avoids Streamlit conflict
   ```
3. (Optional) Add Supabase creds to *Secrets* → `SUPABASE_URL`, `SUPABASE_KEY`.
   If you skip this step the app still works, but data resets when the session ends.

**Why the build kept installing rich 14.0.0**
Streamlit Cloud only reads *requirements.txt*. When we placed the list inside
this Python file it was ignored — so pip grabbed the newest `rich` (14.x).
Pinning in an **external file** fixes the dependency resolver error.
"""
from __future__ import annotations
from datetime import date, timedelta
import streamlit as st
import pandas as pd

# ───────── Optional Supabase import ─────────
try:
    from supabase import create_client, Client  # type: ignore
except ModuleNotFoundError:
    Client = None  # type: ignore

# ───────── Constants ─────────
SECTIONS = ("VARC", "DILR", "QA")
XP_PER_MIN = 1
MEAL_BONUS = 5

# ───────── Helpers ─────────

def today() -> date:
    return date.today()


def today_section() -> str:
    return SECTIONS[today().toordinal() % len(SECTIONS)]


@st.cache_resource(show_spinner=False)
def get_supabase() -> Client | None:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if url and key and Client:
        return create_client(url, key)
    return None

supabase = get_supabase()


def init_session():
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("study_log", [])
    st.session_state.setdefault("meal_log", [])

init_session()

# ───────── On‑boarding ─────────

def onboarding():
    st.title("🎯 Welcome – Set your goals")
    with st.form("onboard"):
        name = st.text_input("Your name")
        exam_date = st.date_input("CAT exam date", value=date(date.today().year, 11, 24))
        target = st.slider("Target percentile", 70, 100, 99)
        macro_goal = st.selectbox("Gym nutrition goal", ("Cut", "Bulk", "Maintain"))
        if st.form_submit_button("Save & Start"):
            profile = {
                "id": "demo" if not supabase else None,
                "name": name,
                "exam_date": exam_date.isoformat(),
                "target_percentile": target,
                "macro_goal": macro_goal,
                "streak": 0,
                "xp": 0,
                "last_active": today().isoformat(),
            }
            if supabase:
                resp = supabase.table("users").insert(profile).execute()
                profile["id"] = resp.data[0]["id"]
            st.session_state.profile = profile
            st.experimental_rerun()

# ───────── Gamification ─────────

def award_xp(amount: int):
    st.session_state.profile["xp"] += amount


def bump_streak():
    last = st.session_state.profile.get("last_active")
    if last == today().isoformat():
        return
    st.session_state.profile["streak"] += 1
    st.session_state.profile["last_active"] = today().isoformat()

# ───────── Pages ─────────

def page_home():
    p = st.session_state.profile
    st.title("🧠 CATPrep × 🍗 MacroTracker")
    st.metric("Streak", f"{p['streak']} 🔥")
    st.metric("XP", p["xp"])
    st.info(f"Today’s focus: **{today_section()}** · Target study: **90 mins**")


def page_study():
    st.header("📚 Study Session")
    mins = st.number_input("Minutes just studied", 0, 180, step=5)
    if st.button("Log study") and mins > 0:
        st.session_state.study_log.append({"date": today(), "minutes": int(mins)})
        if supabase:
            supabase.table("study_log").insert({
                "user_id": st.session_state.profile["id"],
                "date": today().isoformat(),
                "minutes": int(mins),
            }).execute()
        award_xp(mins * XP_PER_MIN)
        bump_streak()
        st.balloons()
        st.success("Logged & XP awarded!")


def page_meals():
    st.header("🍽️ Meal Logger")
    cols = st.columns(5)
    item = cols[0].text_input("Item")
    cal = cols[1].number_input("Cal", 0)
    protein = cols[2].number_input("Protein", 0)
    carbs = cols[3].number_input("Carbs", 0)
    fat = cols[4].number_input("Fat", 0)
    if st.button("Add meal") and item:
        entry = {"date": today(), "item": item, "cal": int(cal), "protein": int(protein), "carbs": int(carbs), "fat": int(fat)}
        st.session_state.meal_log.append(entry)
        if supabase:
            supabase.table("meal_log").insert({"user_id": st.session_state.profile["id"], **entry}).execute()
        award_xp(MEAL_BONUS)
        bump_streak()
        st.toast("Meal saved 🍏")


def page_dashboard():
    st.header("📊 Dashboard – Last 7 Days")
    df = pd.DataFrame(st.session_state.study_log)
    if not df.empty:
        last7 = df[df["date"] >= today() - timedelta(days=6)]
        st.line_chart(last7, x="date", y="minutes")
    else:
        st.info("No study data yet.")

# ───────── Router ─────────
if st.session_state.profile is None:
    onboarding()
    st.stop()

st.sidebar.title("Menu")
page = st.sidebar.radio("Navigate", ("Home", "Study", "Meals", "Dashboard"))

if page == "Home":
    page_home()
elif page == "Study":
    page_study()
elif page == "Meals":
    page_meals()
else:
    page_dashboard()
