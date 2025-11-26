# auth/auth_json_module.py (FIXED)
"""
Fixed authentication module with correct return values
"""

import streamlit as st
import bcrypt
from datetime import datetime, timedelta
import extra_streamlit_components as stx
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
auth_dir = os.path.join(current_dir, "Auth")
if auth_dir not in sys.path:
    sys.path.append(auth_dir)

from auth.json_module import (
    get_user, get_user_count, add_user, update_password,
    set_reset_token, get_user_by_token, update_user, delete_user,
    send_reset_email, get_all_users
)

# ===== COOKIE MANAGER =====
def get_cookie_manager():
    return stx.CookieManager()

# ===== LOGIN TAB =====
def login_tab(cookie_manager):
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    remember_me = st.checkbox("Remember me", key="login_remember")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Login", key="login_btn"):
            user = get_user(email)
            if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                st.session_state.logged_in = True
                st.session_state.user = user
                if remember_me:
                    cookie_manager.set("auth_email", email, expires_at=datetime.now() + timedelta(days=30))
                    cookie_manager.set("auth_password", password, expires_at=datetime.now() + timedelta(days=30))
                else:
                    if "auth_email" in cookie_manager.cookies:
                        cookie_manager.delete("auth_email")
                        cookie_manager.delete("auth_password")
                st.rerun()
            else:
                st.error("Invalid email or password")

    with col2:
        if st.button("Forgot Password?", key="forgot_btn"):
            if not email:
                st.warning("Enter your email above first.")
            else:
                user = get_user(email)
                if not user:
                    st.error("No account found with that email.")
                else:
                    token = set_reset_token(email)
                    send_reset_email(email, token)

# ===== RESET PASSWORD =====
def reset_password_ui(token):
    user = get_user_by_token(token)
    if not user:
        st.error("Invalid or expired reset link.")
        return

    st.subheader("Reset Password")
    new_pass = st.text_input("New Password", type="password", key="reset_new_pass")
    if st.button("Update Password", key="reset_update_btn"):
        update_password(user["email"], new_pass)
        st.success("Password updated! You can now log in.")

# ===== SIGNUP TAB =====
def signup_tab():
    st.subheader("Sign Up")
    name = st.text_input("Full Name", key="signup_name")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Password", type="password", key="signup_password")
    address = st.text_area("Address", key="signup_address")
    company = st.text_input("Company", key="signup_company")
    phone = st.text_input("Phone", key="signup_phone")

    if st.button("Sign Up", key="signup_btn"):
        if get_user(email):
            st.error("Email already registered.")
        else:
            add_user(name, email, password, address, company, phone)
            if get_user_count() == 1:
                st.success("Account created! You are the admin. Please log in.")
            else:
                st.success("Account created! Please log in.")

# ===== ADMIN PANEL =====
def admin_panel():
    st.subheader("👨‍💼 Admin Control Panel")
    
    search_query = st.text_input("Search by name or email", key="admin_search")
    users = get_all_users(search_query)

    st.write(f"**Total Users:** {len(users)}")
    
    for user in users:
        with st.expander(f"{user['name']} ({user['email']}) {'🔑 ADMIN' if user.get('is_admin') else '👤 USER'}"):
            name = st.text_input("Name", value=user.get("name", ""), key=f"name_{user['id']}")
            email = st.text_input("Email", value=user.get("email", ""), key=f"email_{user['id']}")
            address = st.text_area("Address", value=user.get("address", ""), key=f"address_{user['id']}")
            company = st.text_input("Company", value=user.get("company", ""), key=f"company_{user['id']}")
            phone = st.text_input("Phone", value=user.get("phone", ""), key=f"phone_{user['id']}")
            is_admin = st.checkbox("Admin", value=user.get("is_admin", False), key=f"admin_{user['id']}")

            if st.button("Save Changes", key=f"save_{user['id']}"):
                try:
                    update_user(user['id'], name, email, address, company, phone, is_admin)
                    st.success("User updated")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if st.button("Delete User", key=f"delete_{user['id']}"):
                try:
                    delete_user(user['id'])
                    st.warning("User deleted")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# ===== MAIN AUTH FUNCTION =====
def auth_ui():
    """
    Main authentication UI function
    
    Returns:
        bool: True if user is admin, False otherwise
    """
    # Initialize session state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None

    cookie_manager = get_cookie_manager()
    query_params = st.query_params

    # RESET PASSWORD MODE
    if "reset_token" in query_params:
        reset_password_ui(query_params["reset_token"])
        return False  # Not admin

    # AUTO-LOGIN FROM COOKIES
    if not st.session_state.logged_in:
        saved_email = cookie_manager.get("auth_email")
        saved_password = cookie_manager.get("auth_password")
        if saved_email and saved_password:
            user = get_user(saved_email)
            if user and bcrypt.checkpw(saved_password.encode(), user["password_hash"].encode()):
                st.session_state.logged_in = True
                st.session_state.user = user

    # CHECK IF LOGGED IN
    if st.session_state.logged_in:
        user = st.session_state.user
        
        # Check if user is admin
        if user and user.get("is_admin", False):
            # Show admin header with logout
            col1, col2 = st.columns([6, 1])
            with col1:
                st.title("🔐 Admin Dashboard")
            with col2:
                if st.button("Logout", key="admin_logout_btn"):
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    try:
                        cookie_manager.delete("auth_email")
                        cookie_manager.delete("auth_password")
                    except:
                        pass
                    st.rerun()
            
            # Show admin panel
            admin_panel()
            return True  # IS ADMIN
        else:
            # Regular user - show nothing here, let main app handle it
            return False  # NOT ADMIN

    # NOT LOGGED IN - Show login/signup
    st.markdown(
        """
        <div style="font-size: 2rem; margin-top: 0px; margin-bottom: 10px; font-weight: bold;">
            🔐 Authentication
        </div>
        """,
        unsafe_allow_html=True
    )

    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        login_tab(cookie_manager)
    with tab2:
        signup_tab()

    return False  # Not logged in, so not admin