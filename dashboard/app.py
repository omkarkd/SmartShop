import os
import sys
import streamlit as st
from datetime import datetime, timezone

# Support both 'dashboard.auth' (Docker/PYTHONPATH) and bare 'auth' (buildpack with Root Directory)
try:
    from dashboard.auth import seed_admin_user, authenticate, is_session_expired
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from auth import seed_admin_user, authenticate, is_session_expired

# ── Lifecycle setup ──
seed_admin_user()

st.set_page_config(
    page_title="SmartShop Admin",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state defaults ──
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "login_time" not in st.session_state:
    st.session_state.login_time = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

# ── Session expiry check ──
if st.session_state.authenticated and is_session_expired(st.session_state.login_time):
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.login_time = None
    st.warning("Session expired — please log in again.")
    st.rerun()

st.markdown("""
<style>
.login-container { max-width: 400px; margin: 100px auto; padding: 40px;
    background: #1e293b; border-radius: 12px; text-align: center; }
.login-container h1 { color: #38bdf8; }
.main-header { margin-bottom: 24px; }
.stApp { background: #0f172a; }
</style>
""", unsafe_allow_html=True)

# ── Login gate ──
if not st.session_state.authenticated:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h1>Admin Panel</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8'>SmartShop Performance Dashboard</p>")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Sign In", type="primary", use_container_width=True):
        user = authenticate(username, password)
        if user:
            st.session_state.authenticated = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.session_state.login_time = datetime.now(timezone.utc)
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ── Dashboard UI ──
st.markdown("<h1 style='margin-bottom:0'> Admin Dashboard</h1>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    st.markdown(
        f"<span style='color:#94a3b8;font-size:14px'>"
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — "
        f"Logged in as <b>{st.session_state.username}</b> ({st.session_state.role})"
        f"</span>",
        unsafe_allow_html=True,
    )
with col4:
    if st.button("Sign Out", type="secondary"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.login_time = None
        st.rerun()

st.markdown("---")

# ── Tabs (role-gated) ──
is_admin = st.session_state.role == "admin"
tab_labels = [" Dashboard ", " Scraping Runs ", " Database "]
tab_icons = ["", "", ""]
if is_admin:
    tab_labels.append(" Scraper Control ")

tabs = st.tabs(tab_labels)

with tabs[0]:
    from dashboard.pages.dashboard import show
    show()
with tabs[1]:
    from dashboard.pages.runs import show
    show()
with tabs[2]:
    from dashboard.pages.database import show
    show()
if is_admin and len(tabs) > 3:
    with tabs[3]:
        from dashboard.pages.control import show
        show()
