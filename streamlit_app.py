import streamlit as st
import datetime as dt

st.set_page_config(page_title="Pocket App", page_icon="📱", layout="centered")

st.title("📱 Pocket App – Hello, World!")

name = st.text_input("Your name", value="Prateek")
st.write(f"👋 Hi {name}, it’s {dt.datetime.now().strftime('%A %I:%M %p')}")

if st.button("Say on-screen hello"):
    st.success(f"Nice! Enjoy coding on {dt.date.today():%B %Y}.")
