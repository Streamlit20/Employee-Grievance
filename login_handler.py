import os
import msal
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "569600e6-05d0-48eb-828d-e1441782146c")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "0R78Q~LmjzlB_YFqm67G8joyzKOo0sLSyTW1JayT")
TENANT_ID = os.getenv("AZURE_TENANT_ID", "7571a489-bd29-4f38-b9a6-7c880f8cddf0")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["User.Read"]
REDIRECT_URI = os.getenv("AAD_REDIRECT_URI", "https://sonata-employee-grievance.streamlit.app")
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_SEC", "3600"))
ADMIN_EMAILS = [x.strip().lower() for x in os.getenv("ADMIN_EMAILS", "").split(",") if x.strip()]


def create_msal_app():
    return msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )


def get_auth_code():
    """Safely retrieves the 'code' param from URL."""
    try:
        return st.query_params.get("code")
    except Exception:
        qp = st.experimental_get_query_params()
        vals = qp.get("code")
        return vals[0] if vals else None


def handle_login_flow():
    """Automatically initiates Azure AD login flow when user is not authenticated."""
    # Check if already logged in
    if "user" in st.session_state:
        return st.session_state["user"]

    # Prevent reusing old ?code param after logout
    if "logout" in st.query_params:
        st.query_params.clear()

    # If not logged in, check if we already have an auth code in the URL
    code = get_auth_code()
    app = create_msal_app()

    # If no auth code — redirect immediately to Microsoft login
    if not code:
        auth_url = app.get_authorization_request_url(scopes=SCOPE, redirect_uri=REDIRECT_URI)
        st.markdown(f"<meta http-equiv='refresh' content='0; url={auth_url}'>", unsafe_allow_html=True)
        st.stop()

    # If returning from login, acquire token
    result = app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    if "access_token" in result:
        claims = result.get("id_token_claims", {})
        email = (claims.get("preferred_username") or claims.get("email") or "").lower()
        if not email:
            st.error("Login failed: No email found.")
            return None

        name = email.split("@")[0].title()
        role = "admin" if email in ADMIN_EMAILS else "employee"
        st.session_state.user = {"name": name, "email": email, "role": role}
        st.rerun()

    return None
