import os
from typing import List, Optional
import requests
from msal import ConfidentialClientApplication
from mcp.types import TextContent

GRAPH = "https://graph.microsoft.com/v1.0"
TENANT_ID = "7571a489-bd29-4f38-b9a6-7c880f8cddf0"
CLIENT_ID = "569600e6-05d0-48eb-828d-e1441782146c"
CLIENT_SECRET = "0R78Q~LmjzlB_YFqm67G8joyzKOo0sLSyTW1JayT"

def _get_app_token() -> str:
    app = ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}"
    )
    res = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in res:
        raise RuntimeError(f"Token acquisition failed: {res}")
    return res["access_token"]

def _addr_list(emails: Optional[List[str]]) -> List[dict]:
    return [{"emailAddress": {"address": e}} for e in emails or []]

# --- for MCP use ---

def send_email(sender_user_id: str, to_emails: List[str], subject: str, html_body: str) -> TextContent:
        try:
            token = _get_app_token()
            message = {
                "message": {
                    "subject": subject,
                    "importance": "Normal",
                    "body": {"contentType": "HTML", "content": html_body},
                    "toRecipients": _addr_list(to_emails),
                },
                "saveToSentItems": "true"
            }
            url = f"{GRAPH}/users/{sender_user_id}/sendMail"
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=message,
                timeout=30
            )
            if r.status_code == 202:
                return TextContent(type="text", text=f"Email Sent Successfully to {to_emails}.")
            else:
                return TextContent(type="text", text=f"Send failed [{r.status_code}]: {r.text}")
        except Exception as e:
            return TextContent(type="text", text=f"Error sending email: {str(e)}")

# --- direct callable for internal scripts ---
def send_email(sender_user_id: str, to_emails: List[str], subject: str, html_body: str):
    """Direct use version for other scripts (like grievance.py)."""
    token = _get_app_token()
    message = {
        "message": {
            "subject": subject,
            "importance": "Normal",
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": _addr_list(to_emails),
        },
        "saveToSentItems": "true"
    }
    url = f"{GRAPH}/users/{sender_user_id}/sendMail"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=message,
        timeout=30
    )
    if r.status_code != 202:
        raise RuntimeError(f"Send failed [{r.status_code}]: {r.text}")
    return f"✅ Email sent successfully to {to_emails}"
