# streamlit_app.py – Stand‑alone version (single file)
"""
CAT Prep & Gym‑Nutrition Tracker – MVP

Copy this single file into the root of your GitHub repo, commit, and point
Streamlit Cloud’s **Main file path** to **streamlit_app.py**. No extra folders
or splitting required – everything lives here, so you won’t hit the earlier
`SyntaxError` caused by pasting multiple modules into one script.

Dependencies (add to requirements.txt):
    streamlit==1.35.0
    pandas
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import date

# ────────────────────────────────────────────────
# 🔧  Session‑state helpers
# ────────────────────────────────────────────────

def init_state() -> None:
    """Initialise lists the first time the app runs in a session."""
    for key, default in (
        ("study_log", []),           # list[dict(date, minutes)]
        ("meal_log",  []),           # list[dict(date, item, cal, protein, carbs, fat)]
    ):
        if key not in st.session_state:
            st.session_state[key] = default


def today() -> date:
    return date.today()


# ────────────────────────────────────────────────
# 📚  Study helpers
# ────────────────────────────────────────────────

STUDY_SECTIONS = ("VARC", "DILR", "QA")


def todays_section() -> str:
    idx = today().toordinal() % len(STUDY_SECTIONS)
    return STUDY_SECTIONS[idx]


def log_study(mins: int) -> None:
    st.session_state.study_log.append({"date": today(), "minutes": mins})


def last7_study_df() -> pd.DataFrame:
    df = pd.DataFrame(st.session_state.study_log)
    if df.empty:
        return df
    last7 = df[df["date"] >= today() - pd.Timedelta(days=6)]
    return last7.groupby("date", as_index=False)["minutes"].sum()


# ────────────────────────────────────────────────
# 🍽️  Nutrition helpers
# ────────────────────────────────────────────────

def add_meal(entry: dict[str, int | str]) -> None:
    entry["date"] = today()
    st.session_state.meal_log.append(entry)


def today_macros() -> dict[str, int]:
    df = pd.DataFrame(st.session_state.meal_log)
    if df.empty:
        return {}
    today_df = df[df["date"] == today()]
    if today_df.empty:
        return {}
    totals = {
        k: int(today_df[k].sum())
        for k in ("cal", "protein", "carbs", "fat")
    }
    return totals


# ────────────────────────────────────────────────
# 🖼️  UI Pages
# ────────────────────────────────────────────────

def home_page():
    st.title("🧠 CATPrep × 🍗 MacroTracker")
    st.markdown(
        "Plan & track your daily CAT study sessions **and** gym‑friendly"
        " nutrition in one place. Use the sidebar to switch pages."
    )

    st.info(
        f"Today’s recommended section: **{todays_section()}** · Target study: **90 mins**"
    )


def study_page():
    st.header("📚 Log Study Time")
    st.write(f"Today’s focus section: **{todays_section()}**")

    mins = st.number_input("Minutes you actually studied", min_value=0, step=5)
    if st.button("Save study time"):
        log_study(int(mins))
        st.success("Saved! Check Dashboard for progress →")


def meal_page():
    st.header("🍽️ Log a Meal / Snack")
    cols = st.columns(5)
    item = cols[0].text_input("Item")
    cal = cols[1].number_input("Cal", 0)
    protein = cols[2].number_input("Protein", 0)
    carbs = cols[3].number_input("Carbs", 0)
    fat = cols[4].number_input("Fat", 0)

    if st.button("Add meal"):
        add_meal({"item": item, "cal": cal, "protein": protein, "carbs": carbs, "fat": fat})
        st.toast("Meal logged!", icon="🍏")

    macros = today_macros()
    if macros:
        st.subheader("Today’s Macro Totals")
        st.dataframe(pd.DataFrame([macros]))


def dashboard_page():
    st.header("📊 Dashboard")
    st.subheader("Study Minutes – Last 7 Days")
    df = last7_study_df()
    if df.empty:
        st.info("No study data yet – log some time!")
    else:
        st.line_chart(df, x="date", y="minutes")

    st.subheader("Today’s Macro Snapshot")
    macros = today_macros()
    if macros:
        st.dataframe(pd.DataFrame([macros]))
    else:
        st.info("No meals logged yet.")


# ────────────────────────────────────────────────
# 🚀  Main
# ────────────────────────────────────────────────

def main():
    st.sidebar.title("Menu")
    page = st.sidebar.radio(
        "Go to", ("Home", "Study Log", "Meal Log", "Dashboard"),
        captions=["Intro & today’s focus", "Record study minutes", "Record meals", "View progress"],
    )

    if page == "Home":
        home_page()
    elif page == "Study Log":
        study_page()
    elif page == "Meal Log":
        meal_page()
    elif page == "Dashboard":
        dashboard_page()


if __name__ == "__main__":
    init_state()
    st.set_page_config(page_title="CATPrep & MacroTracker", page_icon="💪", layout="centered")
    main()
