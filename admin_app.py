import streamlit as st
from datetime import datetime, timezone

st.set_page_config(
    page_title="SmartShop Admin",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "admin_page" not in st.session_state:
    st.session_state.admin_page = "Dashboard"

st.markdown("""
<style>
.login-container { max-width: 400px; margin: 100px auto; padding: 40px;
    background: #1e293b; border-radius: 12px; text-align: center; }
.login-container h1 { color: #38bdf8; }
.main-header { margin-bottom: 24px; }
.stApp { background: #0f172a; }
</style>
""", unsafe_allow_html=True)

if not st.session_state.admin_logged_in:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h1>Admin Panel</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8'>SmartShop Performance Dashboard</p>")
    username = st.text_input("Username", value="admin", key="login_user")
    password = st.text_input("Password", value="admin", type="password", key="login_pass")
    if st.button("Sign In", type="primary", use_container_width=True):
        if username == "admin" and password == "admin":
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown("<h1 style='margin-bottom:0'> Admin Dashboard</h1>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown(f"<span style='color:#94a3b8;font-size:14px'>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</span>",
                    unsafe_allow_html=True)
    with col4:
        if st.button("Sign Out", type="secondary"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.markdown("---")
    tabs = st.tabs([" Dashboard ", " Scraping Runs ", " Database ", " Scraper Control "])

    with tabs[0]:
        from pages.dashboard import show
        show()
    with tabs[1]:
        from pages.runs import show
        show()
    with tabs[2]:
        from pages.database import show
        show()
    with tabs[3]:
        from pages.control import show
        show()
