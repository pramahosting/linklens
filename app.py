# ==============================================
# app_test.py
# ==============================================
import streamlit as st
from auth.auth_json_module import auth_ui
import pandas as pd
from backend.linkedin_scraper import LinkedInScraper

from PIL import Image
import io
import base64


st.set_page_config(page_title="LinkedIn Scraper", layout="wide")

# Always render title at top left
st.set_page_config(page_title="LinkedIn Scraper", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_title, col_right = st.columns([6, 2])  # Define these columns before using them

with col_title:
    # Load and resize the uploaded image
    img_path = r"C:\Pramod\Prama AI Agents\Human Resources Agents\LinkLens\Screenshot 2025-11-25 150845.png"
    img = Image.open(img_path)
    img = img.resize((40, 40))  # resize to emoji size

    # Convert image to base64 to embed inline
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Create inline HTML with image and title text
    html_content = f"""
    <div style="display: flex; align-items: center;">
        <img src="data:image/png;base64,{img_base64}" style="width:40px; height:40px; margin-right: 10px;" />
        <h1 style="margin: 0;">Prama Candidate Agent</h1>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

# Run authentication UI and check login
is_admin = auth_ui()

if not st.session_state.get("logged_in", False):
    st.stop()  # stop if not logged in

# Now show Welcome and Logout aligned right on same line as title
with col_right:
    st.markdown(
        f"<div style='text-align: right; margin-top: 25px;'>Welcome <b>{st.session_state.user.get('name', 'User')}!</b></div>",
        unsafe_allow_html=True,
    )
    # Create 2 columns: empty + button, so button shifts right
    empty_col, btn_col = st.columns([3, 2])
    with btn_col:
        if st.button("Logout", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()


# ---------------------------------------------------------
# Country & City Dropdown Data
# ---------------------------------------------------------
country_options = ["", "Australia", "India"]

cities_by_country = {
    "Australia": [
        "All Cities",
        "Sydney", "Melbourne", "Brisbane", "Perth",
        "Adelaide", "Canberra", "Gold Coast", "Hobart"
    ],
    "India": [
        "All Cities",
        "Delhi", "Mumbai", "Bengaluru", "Hyderabad",
        "Chennai", "Pune", "Kolkata", "Ahmedabad"
    ]
}

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    /* Remove padding and margin on the sidebar's main container */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    /* Remove margin on all headers inside the sidebar */
    [data-testid="stSidebar"] h2 {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
        padding: 0 !important;
    }

    /* Reduce vertical spacing around inputs inside sidebar */
    [data-testid="stSidebar"] .stTextInput,
    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stSlider,
    [data-testid="stSidebar"] .stCheckbox,
    [data-testid="stSidebar"] .stButton {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
        padding: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("🔐 LinkedIn Login")
    username_input = st.text_input("LinkedIn Username")
    password_input = st.text_input("LinkedIn Password", type="password")

    st.header("🎯 Search Parameters")
    job_title = st.text_input("Job Title / Role", "Data Scientist")

    # COUNTRY DROPDOWN
    country = st.selectbox("Country", country_options, index=1)

    # CITY DROPDOWN (dependent)
    if country in cities_by_country and country != "":
        city_choice = st.selectbox("City", cities_by_country[country])
        city = "" if city_choice == "All Cities" else city_choice
    else:
        city = ""
        st.selectbox("City", ["All Cities"], index=0, disabled=True)

    max_results = st.slider("Max Results", 10, 100, 20)
    headless = st.checkbox("Run headless", True)

    run_button = st.button("Run Scraper")

# ---------------------------------------------------------
# RUN SCRAPER
# ---------------------------------------------------------
if run_button:
    if not username_input or not password_input:
        st.error("Please provide LinkedIn username and password.")
        st.stop()

    with st.spinner("Starting Playwright browser..."):
        scraper = LinkedInScraper(headless=headless)

    try:
        with st.spinner("Logging into LinkedIn..."):
            scraper.login(username_input, password_input)

        with st.spinner("Searching candidates..."):
            results = scraper.search_candidates(
                job_title,
                country,
                max_results,
                city=city
            )

        if results:
            df = pd.DataFrame(results)[[
                "Name", "Headline", "Current Role",
                "City", "Country", "Qualification",
                "Skills", "LinkedIn Link"
            ]]

            st.success(f"✅ Found {len(df)} profiles!")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False),
                file_name="linkedin_candidates.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No candidates found or search failed.")

    except Exception as e:
        st.error(f"Error: {e}")

    finally:
        scraper.close()
