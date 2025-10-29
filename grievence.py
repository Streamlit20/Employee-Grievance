import os
import io
import time 
import pandas as pd
import streamlit as st
from datetime import datetime
from typing import List, Dict, Any 
from dotenv import load_dotenv
from azure.data.tables import TableServiceClient, TableEntity 
from email_sender import send_email   
from login_handler import handle_login_flow, REDIRECT_URI
# Add these imports at the top of app.py
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
# --------------------------------------------------------------------------------
# CONFIG / CONSTANTS (Merged)
# --------------------------------------------------------------------------------
load_dotenv()

# --- Azure Config (from grievence_3) ---
CONNECTION_STRING = os.getenv("CONNECTION_STRING", "")
GRIEVANCE_TABLE_NAME = "Grievancesraised"
ADMINS_TABLE_NAME = "adminsdetails"

# --- App Config (from grievence_2) ---
CATEGORIES = ["IT", "Facilities", "Finance", "HR", "Other"]
STATUSES = ["Open", "WIP", "Closed"]

# (ADMIN_EMAILS from grievence_2 is no longer needed as we fetch admins from Azure)

# --------------------------------------------------------------------------------
# STYLING (Sonata Theme from grievence_3)
# --------------------------------------------------------------------------------
st.set_page_config(page_title="Employee Grievance Portal", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
.stApp { background-color: #f8f9fa; font-family: 'Poppins', sans-serif; }
.stButton>button {
    width: 100%; border-radius: 8px; border: 1px solid #e0e0e0;
    transition: all 0.2s ease-in-out;
}
.stButton>button:hover { background-color: #f0f0f0; border-color: #c0c0c0; }

.small-muted { color: #6b7280; font-size: 0.9rem; }
.kpi-card {
    border: 1px solid #eee; border-radius: 12px; padding: 15px 20px; background: #fff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 10px;
}
.kpi-title { color:#6b7280; font-weight:600; margin-bottom:6px; font-size:0.9rem; }
.kpi-value {
    display:inline-block; min-width:50px; text-align:center; font-weight:700;
    background:#eef2ff; border-radius:8px; padding:8px 12px; font-size:1.2rem;
    color: #1e40af;
}
.kpi-value.closed { background:#111827; color:#fff; }
.kpi-value.wip { background:#fff7ed; color:#9a3412; }

.badge { display:inline-block; padding:5px 10px; border-radius:999px; font-weight:600; font-size:0.8rem; }
.badge-open { background:#eef2ff; color:#1e40af; }
.badge-wip { background:#fff7ed; color:#9a3412; }
.badge-closed { background:#111827; color:#fff; }

.section-box {
    border: 1px solid #eee; border-radius: 12px; padding: 25px; background: #fff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 20px;
}
.hero-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 4px; color:#1e3a8a; }
.hero-sub { color:#6b7280; font-size: 1rem; margin-bottom: 20px; }

.filter-chip-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.stButton.logout-button > button {
    background-color: #dc3545; color: white; font-weight: bold;
    border: none; padding: 8px 15px; border-radius: 8px; width: auto;
}
.stButton.logout-button > button:hover { background-color: #c82333; }

.comment-history-box {
    background: #f9f9f9; border-radius: 8px; padding: 15px; margin-top: 15px;
    border: 1px solid #eee; max-height: 200px; overflow-y: auto;
}
.comment-entry { border-bottom: 1px dashed #e0e0e0; padding-bottom: 10px; margin-bottom: 10px; }
.comment-entry:last-child { border-bottom: none; }
.comment-meta { font-size: 0.85rem; color: #6b7280; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)
BLOB_CONTAINER_NAME = "grievanceattachements" # Your specified container name

def get_blob_client() -> BlobServiceClient:
    """Gets a client for the Azure Blob Storage service."""
    # Reuses the existing CONNECTION_STRING (declared at the top of app.py)
    return BlobServiceClient.from_connection_string(conn_str=CONNECTION_STRING)

def upload_file_to_blob(file_obj: io.BytesIO, file_name: str) -> str:
    """Uploads a file object to Blob Storage and returns its full URL (without SAS)."""
    try:
        blob_service_client = get_blob_client()
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)
        
        # Ensure container exists (create if not)
        try:
            container_client.create_container()
        except Exception:
            pass # Container likely already exists

        # Upload the file
        blob_client = container_client.get_blob_client(file_name)
        file_obj.seek(0) # Reset pointer to the start of the file
        blob_client.upload_blob(file_obj, overwrite=True)
        
        # Return the base URL of the blob
        return blob_client.url
    except Exception as e:
        print(f"⚠️ Failed to upload file to Blob: {e}")
        return ""

# ---------------------------------------------------
# Azure Blob Helper Function (MODIFIED)
# ---------------------------------------------------

def generate_sas_url(blob_url: str) -> str:
    """
    Generates a secure, short-lived SAS URL for a given blob URL, 
    setting content_disposition to 'inline' to encourage browser viewing.
    """
    try:
        blob_service_client = get_blob_client()
        
        # Extract necessary parts from the blob URL
        blob_name = blob_url.split(f"/{BLOB_CONTAINER_NAME}/")[-1]
        
        # Generate the SAS token for read access, valid for 1 hour
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=BLOB_CONTAINER_NAME,
            blob_name=blob_name,
            account_key=blob_service_client.credential.account_key, # Assumes conn string has key
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
            # THE CRITICAL CHANGE: Force browser to display inline
            content_disposition="inline" 
        )
        
        # Append SAS token to the original URL
        return f"{blob_url}?{sas_token}"
    except Exception as e:
        print(f"⚠️ Failed to generate SAS URL: {e}")
        return blob_url # Fallback to base URL (less secure)

# --------------------------------------------------------------------------------
# EMAIL SENDER (from grievence_3, UPDATED to email all admins)
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------
# EMAIL SENDER (Final Update for 'email' column check)
# --------------------------------------------------------------------------------
def send_grievance_email(grievance_data: Dict[str, Any]):
    """Automatically generate and send an HTML email to all admins with grievance details."""
    try:
        sender_user_id = "So_App_Support@sonata-software.com"

        # 1. Fetch admin entities using the existing cached function
        all_admin_entities = fetch_all_admins()
        admin_emails = []
        for admin in all_admin_entities:
            
            # --- THE FIX ---
            # Explicitly fetch the value from the 'email' column, which you confirmed is present.
            email = admin.get("email")
            # Fallback to RowKey only if 'email' is explicitly missing/empty.
            if not email:
                email = admin.get("RowKey")
                
            if email and "@" in email: # Simple validation
                admin_emails.append(email)
            # ---------------

        if not admin_emails:
            print("⚠️ No admin emails found. Cannot send notification.")
            return

        grievance_id = grievance_data.get("RowKey", "")
        subject = f"New Grievance Raised - {grievance_id}"

        html_body = f"""
        <html><body style="font-family:Arial, sans-serif;">
        <h2 style="color:#1e3a8a;">📢 New Grievance Submitted</h2>
        <p><strong>Grievance ID:</strong> {grievance_data.get("RowKey")}</p>
        <p><strong>Title:</strong> {grievance_data.get("title")}</p>
        <p><strong>Category:</strong> {grievance_data.get("category")}</p>
        <p><strong>Description:</strong> {grievance_data.get("description")}</p>
        <p><strong>Employee:</strong> {grievance_data.get("employee_name")} ({grievance_data.get("employee_email")})</p>
        <p><strong>Created At:</strong> {grievance_data.get("created_at")}</p>
        <p style="color:gray;">Please log in to the Grievance Portal to view or assign this case.</p>
        </body></html>
        """

        # 2. Send to each admin individually
        for email in admin_emails:
            try:
                send_email(
                    sender_user_id=sender_user_id,
                    to_emails=[email], # Send to one admin at a time
                    subject=subject,
                    html_body=html_body
                )
                print(f"✅ Email notification sent to {email}")
            except Exception as ex:
                print(f"⚠️ Failed to send email to {email}: {ex}")

    except Exception as e:
        print(f"⚠️ Top-level email sending failed: {e}")


# --------------------------------------------------------------------------------
# TABLE HELPERS (from grievence_3, replacing Excel logic)
# --------------------------------------------------------------------------------

def get_table_client(name: str):
    """Gets a client for a specific Azure Table."""
    svc = TableServiceClient.from_connection_string(conn_str=CONNECTION_STRING)
    return svc.get_table_client(name)

@st.cache_data
def fetch_all_admins() -> List[Dict[str, Any]]:
    """Fetches all admin user details from Azure Table."""
    try:
        table = get_table_client(ADMINS_TABLE_NAME)
        # Assuming admins have a specific PartitionKey, e.g., 'ADMIN'
        entities = table.query_entities(f"PartitionKey eq 'admin'")
        return [dict(e) for e in entities]
    except Exception as e:
        st.error(f"Error fetching admin list: {e}")
        return []

@st.cache_data
def fetch_all_grievances() -> List[Dict[str, Any]]:
    """Fetches all grievances from Azure Table."""
    try:
        table = get_table_client(GRIEVANCE_TABLE_NAME)
        entities = table.query_entities("PartitionKey eq 'GRIEVANCE'")
        return [dict(e) for e in entities]
    except Exception as e:
        st.error(f"Error fetching grievances: {e}")
        return []

def load_grievances_df() -> pd.DataFrame:
    """Fetches grievances and converts to DataFrame for UI compatibility."""
    grievances_list = fetch_all_grievances()
    if not grievances_list:
        # Return empty DataFrame with correct columns if no data
        return pd.DataFrame(columns=[
            "id", "title", "description", "category",
            "employee_name", "employee_email",
            "status", "assigned_to", "created_at", "updated_at",
            "comments", "attachments", "RowKey"
        ])
    
    df = pd.DataFrame(grievances_list)
    
    # Rename RowKey to id for compatibility with grievence_2's logic
    if "RowKey" in df.columns:
        df = df.rename(columns={"RowKey": "id"})
    
    # Ensure all columns from grievence_2 exist, fill with empty string if not
    for col in ["comments", "assigned_to", "attachments", "status"]:
            if col not in df.columns:
                df[col] = ""
    
    # Fill NaNs in key columns to avoid errors
    df['comments'] = df['comments'].fillna('')
    df['assigned_to'] = df['assigned_to'].fillna('')
    df['attachments'] = df['attachments'].fillna('')
    df['status'] = df['status'].fillna('Open')
    return df

def clear_grievance_cache():
    """Clears the grievance data cache."""
    fetch_all_grievances.clear()
    fetch_all_admins.clear()

def generate_next_id(grievances: List[Dict[str, Any]]) -> str:
    """Generates the next grievance ID (e.g., GRV_05)."""
    max_num = 0
    for g in grievances:
        gid = g.get("RowKey", "")
        if gid.startswith("GRV_"):
            try:
                n = int(gid.split("_")[1])
                max_num = max(max_num, n)
            except: pass
    return f"GRV_{max_num + 1:03d}" # Padded to 3 digits

def create_grievance(new_id: str, title: str, desc: str, category: str, name: str, email: str, attachments: List[str]):
    """Creates a new grievance entity in Azure Table."""
    table = get_table_client(GRIEVANCE_TABLE_NAME)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entity = {
        "PartitionKey": "GRIEVANCE",
        "RowKey": new_id,
        "title": title.strip(),
        "description": desc.strip(),
        "category": category,
        "employee_name": name,
        "employee_email": email,
        "status": "Open",
        "assigned_to": "",
        "created_at": now,
        "updated_at": now,
        "comments": "",
        "attachments": ";".join(attachments),
    }
    table.create_entity(entity=entity)
    send_grievance_email(entity) # Send email on creation
    clear_grievance_cache()

def update_grievance_entity(grievance_id: str, updates: Dict[str, Any]):
    """Updates a single grievance entity in Azure Table."""
    try:
        table = get_table_client(GRIEVANCE_TABLE_NAME)
        # All grievances use 'GRIEVANCE' as PartitionKey
        entity = table.get_entity(partition_key="GRIEVANCE", row_key=grievance_id)
        
        # Apply updates
        for key, value in updates.items():
            entity[key] = value
        
        # Add update timestamp
        entity["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        table.update_entity(entity=entity, mode="replace")
        clear_grievance_cache() # Clear cache after update
    except Exception as e:
        st.error(f"Failed to update grievance: {e}")
        st.stop()


# -------------------------------
# Styling helpers (from grievence_2)
# -------------------------------
def status_badge(s: str) -> str:
    """Returns the HTML for a styled status badge."""
    s = (s or "").strip()
    if s == "Closed":
        klass = "badge badge-closed"
    elif s == "WIP":
        klass = "badge badge-wip"
    else:
        klass = "badge badge-open"
    return f'<span class="{klass}">{s or "Open"}</span>'


# -------------------------------
# Auth (from grievence_2, with logout button)
# -------------------------------
def logout_btn():
    """Displays the logout button and clears MSAL session on logout."""
    st.markdown("""
        <style>
        .stButton.logout-button {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="stButton logout-button">', unsafe_allow_html=True)
        if st.button("Logout", key="logout_button_main", help="Log out of the system", type="secondary"):
            # Clear Streamlit session
            for k in list(st.session_state.keys()):
                del st.session_state[k]

            # Clear browser-side MSAL cookies by reloading with no code parameter
            logout_redirect = REDIRECT_URI.split("?")[0]
            st.markdown(f"<meta http-equiv='refresh' content='0; url={logout_redirect}'>", unsafe_allow_html=True)
            st.stop()
        st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------
# Stats (from grievence_2, requires DataFrame)
# -------------------------------
def stats_kpis(df: pd.DataFrame):
    """Displays KPI cards for grievance counts."""
    col1, col2, col3, col4 = st.columns(4)
    total_count = len(df)
    closed_count = (df["status"]=="Closed").sum()
    wip_count = (df["status"]=="WIP").sum()
    open_count = (df["status"]=="Open").sum()

    with col1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Raised</div><div class="kpi-value">{total_count}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Closed</div><div class="kpi-value closed">{closed_count}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">WIP</div><div class="kpi-value wip">{wip_count}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Open</div><div class="kpi-value">{open_count}</div></div>', unsafe_allow_html=True)


# ---------------------------------------------------
# Dialog Content Function (from grievence_2, UPDATED)
# ---------------------------------------------------
@st.dialog("Grievance Details")
def grievance_dialog_content(grievance_id: str, all_admins: List[Dict[str, Any]] = None):
    """Displays and handles updates for a specific grievance in a dialog."""
    # MODIFIED: Load DataFrame from new function
    df = load_grievances_df()
    
    try:
        row_data = df[df["id"] == grievance_id].iloc[0].to_dict()
    except IndexError:
        st.error("Could not find grievance. It may have been deleted.")
        st.button("Close")
        st.stop()
        
    current_user_name = st.session_state.user["name"]
    current_user_email = st.session_state.user["email"]
    
    # Permissions checks
    is_admin = (st.session_state.user["role"] == "admin")
    is_creator = (row_data["employee_email"].lower() == current_user_email.lower())
    
    # An employee (creator) can comment if the ticket isn't closed
    can_employee_comment = is_creator and row_data["status"] != "Closed"
    is_editable = is_admin or can_employee_comment

    st.subheader(f"Grievance #{row_data['id']}: {row_data['title']}")
    
    with st.form(key=f"dialog_form_{grievance_id}", clear_on_submit=False):
        st.markdown(f"**Description**: {row_data['description']}")
        st.write("")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Category**: {row_data['category']}")
            st.markdown(f"**Employee**: {row_data['employee_name']} ({row_data['employee_email']})")
        with col2:
            created_at_str = str(row_data.get('created_at', ''))
            updated_at_str = str(row_data.get('updated_at', ''))
            created_at = created_at_str.split(' ')[0]
            updated_at = updated_at_str.split(' ')[0]
            st.markdown(f"**Created At**: {created_at}")
            st.markdown(f"**Last Updated**: {updated_at}")
        st.write("")

        # Variables for update logic
        new_status = row_data["status"]
        new_assigned_to = row_data["assigned_to"]
        
        # --- ATTACHMENTS DISPLAY (NEW) ---
        attachments_content = str(row_data.get("attachments", "")).strip()
        
        st.markdown("---")
        st.markdown("<h5>Attachments</h5>", unsafe_allow_html=True)
        
        if attachments_content:
            attachment_urls = [url for url in attachments_content.split(';') if url.strip()]
            
            # Use columns for a cleaner look
            cols = st.columns(3) 
            
            for i, base_url in enumerate(attachment_urls):
                blob_name_full = base_url.split('/')[-1]
                
                # MODIFICATION: Skip the GRV_XXX_ prefix for display
                # Finds the second part after the first two underscores (e.g., GRV_001_filename.ext -> filename.ext)
                display_name = blob_name_full.split('_', 2)[-1] 
                
                # Generate a secure, temporary SAS URL
                sas_url = generate_sas_url(base_url)
                
                with cols[i % 3]: # Cycle through 3 columns
                    st.markdown(
                        f"""
                        <a href="{sas_url}" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; margin-bottom:5px; background-color:#eef2ff; color:#1e40af; border:1px solid #c7d2fe; border-radius:8px; padding:10px;">
                                📎 {display_name}
                            </button>
                        </a>
                        """, unsafe_allow_html=True
                    )
        else:
            st.info("No attachments uploaded for this grievance.")
        # --- END ATTACHMENTS DISPLAY ---
        
        # --- Admin and Creator Action Section ---
        if is_editable:
            st.markdown("---")
            st.markdown("<h5>Update and Comment</h5>", unsafe_allow_html=True)
            
            # ADMIN ONLY FIELDS
            if is_admin:
                # --- CACHE FIX (Part 1) ---
                # If admin list wasn't passed (e.g., admin viewing from employee page),
                # fetch it. Otherwise, use the pre-loaded list.
                if all_admins is None:
                    all_admins = fetch_all_admins()
                
                # Get name, fallback to email if name is missing
                admin_names_set = set(
                    [admin.get('name', admin.get('email')) for admin in all_admins if admin.get('name') or admin.get('email')]
                )
                
                # --- SELF-ASSIGN FIX ---
                # Ensure the current logged-in admin can self-assign
                current_admin_name = st.session_state.user.get("name")
                if current_admin_name:
                    admin_names_set.add(current_admin_name)
                # --- END SELF-ASSIGN FIX ---
                    
                admin_names = sorted(list(admin_names_set)) # Now create the sorted list

                # Assigned To
                current_assigned = str(row_data.get("assigned_to", "")).strip()
                current_assigned = current_assigned if current_assigned in admin_names else ""
                assign_options = [""] + admin_names
                assigned_idx = assign_options.index(current_assigned) if current_assigned in assign_options else 0
                new_assigned_to = st.selectbox("Assign to", options=assign_options, index=assigned_idx, key=f"dialog_assign_{grievance_id}")

                # Status
                current_status = row_data["status"] if row_data["status"] in STATUSES else "Open"
                status_idx = STATUSES.index(current_status) if current_status in STATUSES else 0
                new_status = st.selectbox("Change Status", options=STATUSES, index=status_idx, key=f"dialog_status_{grievance_id}")
            else:
                # Employee (creator) read-only status/assignment display
                st.markdown(f"**Current Status**: {status_badge(row_data['status'])}", unsafe_allow_html=True)
                st.markdown(f"**Assigned To**: {row_data['assigned_to'] or 'Not assigned'}")
            
            # COMMENT FIELD (Visible to Admin and Commenting Employee)
            new_comment = st.text_area(
                "Add new comment",
                value="",
                key=f"dialog_new_comment_{grievance_id}",
                placeholder="Type your comment here...",
                height=80
            )
            
            st.markdown("---") 
            
            # Action Buttons
            if is_admin:
                btn_col1, btn_col2, btn_col3 = st.columns([0.3, 0.4, 0.3])
                save_clicked = btn_col1.form_submit_button("💾 Save Changes", type="primary")
                close_ticket_clicked = btn_col2.form_submit_button("✖ Close Ticket", type="secondary")
                btn_col3.form_submit_button("Cancel", type="secondary") # Just closes dialog
                update_needed = save_clicked or close_ticket_clicked
            
            elif can_employee_comment: # is_creator and not closed
                btn_col1, btn_col2 = st.columns([0.4, 0.6])
                save_clicked = btn_col1.form_submit_button("📝 Add Comment", type="primary", disabled=not new_comment.strip())
                btn_col2.form_submit_button("Close", type="secondary") 
                update_needed = save_clicked and new_comment.strip()
                if save_clicked and not new_comment.strip():
                    st.warning("Please enter a comment to submit.")
                    
        # --- Read-Only View (Other employees or closed tickets) ---
        else: 
            st.markdown("---")
            st.markdown(f"**Current Status**: {status_badge(row_data['status'])}", unsafe_allow_html=True)
            st.markdown(f"**Assigned To**: {row_data['assigned_to'] or 'Not assigned'}")
            st.write("")
            st.form_submit_button("Close", type="primary") # Simply closes the dialog
            update_needed = False
            new_comment = ""
            
        # --- Submission Logic (MODIFIED for Azure) ---
        if update_needed:
            # Comment is mandatory *if* the user is trying to save
            if (is_admin and (save_clicked or close_ticket_clicked)) and not new_comment.strip():
                 st.warning("⚠️ Please add a comment before saving or closing.")
                 st.stop()
            if (can_employee_comment and save_clicked) and not new_comment.strip():
                 st.warning("⚠️ Please add a comment to submit.")
                 st.stop()

            updates_to_make = {}
            
            # Update Admin fields
            if is_admin:
                if new_assigned_to != row_data["assigned_to"]:
                    updates_to_make["assigned_to"] = new_assigned_to
                
                current_status = row_data["status"]
                if close_ticket_clicked:
                    updates_to_make["status"] = "Closed"
                elif new_status != current_status:
                    updates_to_make["status"] = new_status

            # Add Comment logic (applies to admin and commenting employee)
            if new_comment.strip():
                existing_comments = str(row_data.get("comments", "")).strip()
                comment_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {current_user_name}: {new_comment.strip()}"
                
                if existing_comments:
                    updates_to_make["comments"] = f"{existing_comments}\n{comment_line}".strip()
                else:
                    updates_to_make["comments"] = comment_line.strip()
            
            # Only update if there are actual changes
            if updates_to_make:
                update_grievance_entity(grievance_id, updates_to_make)
                st.success("Grievance updated/comment added successfully. Refreshing view...")
            
            st.rerun() # Rerun to close dialog and refresh main page

        # --- Comment History (visible to all) ---
        st.markdown("---")
        st.markdown("<h5>Comment History</h5>", unsafe_allow_html=True)
        
        comments_content = str(row_data.get("comments", "")).strip()

        if comments_content:
            st.markdown('<div class="comment-history-box">', unsafe_allow_html=True)
            # Split comments, filter out empty lines, and reverse for chronological order
            comments_list = [c.strip() for c in comments_content.split('\n') if c.strip()]
            for comment in reversed(comments_list):
                st.markdown(f'<div class="comment-entry"><p>{comment}</p></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No comments yet.")


# -------------------------------
# Admin View (from grievence_2, MODIFIED)
# -------------------------------
def admin_view():
    """Displays the admin dashboard."""
    user = st.session_state.user
    logout_btn() # Placed at the top right

    # --- CACHE FIX (Part 2) ---
    # Pre-load all admins ONCE when admin dashboard loads.
    # This primes the @st.cache_data function.
    all_admins = fetch_all_admins()
    # --- END CACHE FIX ---

    # Header
    col_title, col_user_info = st.columns([0.7, 0.3])
    with col_title:
        st.markdown('<div class="hero-title">Employee Grievance Portal (Admin)</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-sub">Manage, track, and resolve all grievances.</div>', unsafe_allow_html=True)
    with col_user_info:
        st.markdown(f'<p class="small-muted" style="text-align:right;">Logged in as <b>{user["name"]}</b> ({user["role"]})</p>', unsafe_allow_html=True)

    # MODIFIED: Load DataFrame from new function
    df = load_grievances_df()

    # Year-wise filtering (Kept from grievence_2)
    if not df.empty and "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors='coerce')
        df = df.dropna(subset=["created_at"]) # Drop rows where date conversion failed
        years = sorted(list(df["created_at"].dt.year.unique()), reverse=True)
        year_filter = st.selectbox("📅 Filter by Year", ["All"] + [str(y) for y in years], index=0)
        if year_filter != "All":
            df = df[df["created_at"].dt.year == int(year_filter)]

    # Stats
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Dashboard Stats")
    stats_kpis(df)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("All Grievances")

    # Filter chips (Kept from grievence_2)
    if "last_filter" not in st.session_state:
        st.session_state.last_filter = "All"
    status_filter = st.session_state.last_filter
    
    st.markdown('<div class="filter-chip-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, label in enumerate(["All", "Open", "WIP", "Closed"]):
        with cols[i]:
            button_type = "primary" if status_filter == label else "secondary"
            if st.button(label, key=f"tab_{label}", help=f"Filter by {label} status", use_container_width=True,
                         on_click=lambda l=label: st.session_state.__setitem__("last_filter", l),
                         type=button_type):
                pass
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Search (Kept from grievence_2)
    q = st.text_input("Search by title, description, employee, category", "", key="admin_search_query", placeholder="Search tickets...")
    filtered = df.copy()
    if status_filter != "All":
        filtered = filtered[filtered["status"] == status_filter]
    if q:
        ql = q.lower()
        filtered = filtered[
            filtered.apply(
                lambda r: any(
                    ql in str(r[c]).lower()
                    for c in ["id", "title", "description", "employee_name", "employee_email", "category", "assigned_to", "status"]
                ),
                axis=1,
            )
        ]

    # Grievance List Display (Kept from grievence_2)
    if filtered.empty:
        st.info("No grievances match the filter.")
    else:
        filtered_for_display = filtered.copy()
        filtered_for_display["Status"] = filtered_for_display["status"].apply(status_badge)
        
        # Sort by created_at descending (latest first)
        sorted_df = filtered_for_display.sort_values("created_at", ascending=False)
        
        # Render header row
        header_cols = st.columns([0.1, 0.25, 0.15, 0.15, 0.15, 0.1, 0.1])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Title**")
        header_cols[2].markdown("**Category**")
        header_cols[3].markdown("**Employee**")
        header_cols[4].markdown("**Assigned To**")
        header_cols[5].markdown("**Status**")
        header_cols[6].markdown("**View**")
        st.markdown("---")

        # Render data rows
        for _, row in sorted_df.iterrows():
            row_cols = st.columns([0.1, 0.25, 0.15, 0.15, 0.15, 0.1, 0.1])
            row_cols[0].write(row["id"])
            row_cols[1].write(row["title"])
            row_cols[2].write(row["category"])
            row_cols[3].write(row["employee_name"])
            row_cols[4].write(row["assigned_to"] or "Unassigned")
            row_cols[5].markdown(row["Status"], unsafe_allow_html=True)
            
            # "View" button using st.dialog
            with row_cols[6]:
                # --- CACHE FIX (Part 3) ---
                # Pass the pre-loaded 'all_admins' list into the dialog
                st.button("👁️ View", key=f"view_admin_{row['id']}", help="View Details", type="secondary",
                          on_click=lambda id=row['id'], admins=all_admins: grievance_dialog_content(id, admins))
                # --- END CACHE FIX ---
            st.markdown("---")

    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------
# Employee View (from grievence_2, MODIFIED)
# ---------------------------------------------------
def employee_view():
    """Displays the employee view, allowing submission and tracking of their own tickets."""
    user = st.session_state.user
    logout_btn() # Placed at the top right

    # Header
    col_title, col_user_info = st.columns([0.7, 0.3])
    with col_title:
        st.markdown('<div class="hero-title">Employee Grievance Portal</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-sub">Raise, track, and resolve your grievances.</div>', unsafe_allow_html=True)
    with col_user_info:
        st.markdown(f'<p class="small-muted" style="text-align:right;">Logged in as <b>{user["name"]}</b> ({user["role"]})</p>', unsafe_allow_html=True)

    # MODIFIED: Load DataFrame from new function
    df = load_grievances_df()
    mine = df[df["employee_email"].str.lower() == user["email"].lower()]

    # Stats (for this employee only)
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Your Grievance Stats")
    stats_kpis(mine)
    st.markdown('</div>', unsafe_allow_html=True)

    # Raise new grievance (Submission logic from grievence_3)
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Raise a New Grievance")
    with st.form("raise_grievance"):
        title = st.text_input("Title", placeholder="Brief issue summary", max_chars=100)
        desc = st.text_area("Description", placeholder="Describe the issue and context in detail. Include any relevant steps or observations.")
        category = st.selectbox("Category", options=CATEGORIES, index=0)
        files = st.file_uploader( # 'files' from grievence_3
                        "Attach file(s) (Optional)",
                        type=["pdf", "jpg", "png", "docx", "xlsx"],
                        accept_multiple_files=True)
        
        st.markdown('<div style="text-align:right; margin-top:15px;">', unsafe_allow_html=True)
        submitted = st.form_submit_button("Submit Grievance", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- SUBMISSION LOGIC (Updated for Blob Storage) ---
    if submitted:
        if not title.strip():
            st.error("Please enter a title before submitting.")
        else:
            with st.spinner("Submitting your grievance..."):
                # Calculate ID *once*
                all_rows = fetch_all_grievances()
                new_id = generate_next_id(all_rows)
                
                attachments = []
                if files:
                    # Upload each file to Azure Blob Storage
                    for f in files:
                        # Create a unique blob name using the requested convention: GRV_XXX_filename.ext
                        # We use the calculated new_id here (e.g., GRV_005)
                        safe_name = "".join(c for c in f.name if c.isalnum() or c in ('.', '_', '-')).strip()
                        blob_filename = f"{new_id}_{safe_name}" 
                        
                        # Upload and get the base URL
                        blob_url = upload_file_to_blob(f, blob_filename)
                        if blob_url:
                            # Store the full base URL in the Table Storage
                            attachments.append(blob_url)
                        else:
                            st.warning(f"Could not save attachment {f.name} to Azure.")
                
                # Pass all info to create_grievance
                create_grievance(new_id, title, desc, category, user["name"], user["email"], attachments)
            
            st.success(f"✅ Grievance {new_id} submitted successfully! An email notification has been sent.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    # --- END SUBMISSION LOGIC ---


    # List my grievances (Display logic from grievence_2)
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Your Submitted Grievances")
    
    # Filter chips
    if "emp_filter" not in st.session_state:
        st.session_state.emp_filter = "All"
    filter_status = st.session_state.emp_filter
    
    st.markdown('<div class="filter-chip-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, lbl in enumerate(["All", "Open", "WIP", "Closed"]):
        with cols[i]:
            button_type = "primary" if filter_status == lbl else "secondary"
            if st.button(lbl, key=f"emp_tab_{lbl}", help=f"Filter by {lbl} status", use_container_width=True,
                         on_click=lambda l=lbl: st.session_state.__setitem__("emp_filter", l),
                         type=button_type):
                pass
    st.markdown('</div>', unsafe_allow_html=True)

    # Search
    q = st.text_input("Search by title, description, category", key="emp_search_query", placeholder="Search your tickets...")
    filtered = mine.copy()
    if filter_status != "All":
        filtered = filtered[filtered["status"]==filter_status]
    if q:
        ql = q.lower()
        filtered = filtered[
            filtered.apply(
                lambda r: any(ql in str(r[c]).lower() for c in ["id", "title","description","category","status","assigned_to"]),
                axis=1
            )
        ]
        
    if filtered.empty:
        st.info("You haven't submitted any grievances yet or none match the filter.")
    else:
        filtered_for_display = filtered.copy()
        filtered_for_display["Status"] = filtered_for_display["status"].apply(status_badge)
        
        # Sort by created_at descending (latest first)
        if "created_at" in filtered_for_display.columns:
             filtered_for_display["created_at"] = pd.to_datetime(filtered_for_display["created_at"], errors='coerce')
             sorted_df = filtered_for_display.sort_values("created_at", ascending=False)
        else:
             sorted_df = filtered_for_display # Fallback
        
        
        # Render header row
        header_cols = st.columns([0.1, 0.35, 0.15, 0.15, 0.1, 0.1]) 
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Title**")
        header_cols[2].markdown("**Category**")
        header_cols[3].markdown("**Assigned To**")
        header_cols[4].markdown("**Status**")
        header_cols[5].markdown("**View**")
        st.markdown("---")

        # Render data rows
        for _, row in sorted_df.iterrows():
            row_cols = st.columns([0.1, 0.35, 0.15, 0.15, 0.1, 0.1])
            row_cols[0].write(row["id"])
            row_cols[1].write(row["title"])
            row_cols[2].write(row["category"])
            row_cols[3].write(row["assigned_to"] or "Unassigned")
            row_cols[4].markdown(row["Status"], unsafe_allow_html=True)
            
            # "View" button for st.dialog
            with row_cols[5]:
                st.button("👁️ View", key=f"view_employee_{row['id']}", help="View Details", type="secondary",
                          on_click=lambda id=row['id']: grievance_dialog_content(id))
            st.markdown("---")

    st.markdown('</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------------
# REFRESH/AUTH HANDLING (from grievence_3)
# --------------------------------------------------------------------------------
def show_redirect_screen():
    """Displays a loading spinner while auth is checked."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
        <div style="text-align:center;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;background:linear-gradient(135deg,#f5f7ff,#dce4ff);">
            <h1 style="color:#1e3a8a;font-weight:800;margin-bottom:8px;">Redirecting to Grievance Portal...</h1>
            <p style="color:#4b5563;font-size:1.1rem;">Please wait while we verify your login.</p>
            <div class="loader"></div>
            <style>
                .loader{border:6px solid #f3f3f3;border-top:6px solid #2563eb;border-radius:50%;width:60px;height:60px;animation:spin 1s linear infinite;margin-top:30px;}
                @keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}
            </style>
        </div>""", unsafe_allow_html=True)
    time.sleep(5) # Give a moment for the spinner to be seen
    placeholder.empty()

def safe_load_dashboard():
    """Handles login flow with a persistent redirect screen."""
    placeholder = None
    if "user" not in st.session_state or not st.session_state["user"]:
        placeholder = show_redirect_screen() # <-- Show screen, get placeholder
        try:
            user = handle_login_flow() # <-- This is the long-running task
        except Exception as e:
            if placeholder:
                placeholder.empty() # <-- Clear placeholder on error
            st.error(f"Authentication failed: {e}. Redirecting to login...")
            st.markdown(f"<meta http-equiv='3; url={REDIRECT_URI.split('?')[0]}'>", unsafe_allow_html=True)
            st.stop()
    else:
        user = st.session_state["user"]
    
    if placeholder:
        placeholder.empty() # <-- Clear placeholder on success
    
    if not user or "role" not in user:
        st.markdown("<h3>Session expired or invalid. Redirecting to login...</h3>", unsafe_allow_html=True)
        time.sleep(2)
        # Clear session just in case
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.markdown(f"<meta http-equiv='0; url={REDIRECT_URI.split('?')[0]}'>", unsafe_allow_html=True)
        st.stop()
    
    return user

# -------------------------------
# App Entrypoint (Using grievence_3 logic)
# -------------------------------

# Load dashboard with new auth flow
user = safe_load_dashboard()

# Once logged in, load respective dashboard (from grievence_2)
role = user["role"]
if role == "admin":
    admin_view()
else:
    employee_view()
