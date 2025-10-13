import os
import io
import pandas as pd
import streamlit as st
from datetime import datetime

# -------------------------------
# Config
# -------------------------------
GRIEVANCE_FILE = "sample_grievances.xlsx"
USERS_FILE = "sample_users.xlsx"
CATEGORIES = ["IT", "Facilities", "Finance", "HR", "Other"]
STATUSES = ["Open", "WIP", "Closed"]

# -------------------------------
# Utilities: bootstrap files
# -------------------------------
def ensure_users_file():
    """Ensures the users file exists with default entries."""
    if not os.path.exists(USERS_FILE):
        # Simple seed: 2 admins + 6 employees
        df = pd.DataFrame([
            {"name": "Alice Johnson",   "email": "alice@company.com",   "role": "admin"},
            {"name": "Admin Two",       "email": "admin2@company.com",  "role": "admin"},
            {"name": "Bob Smith",       "email": "bob@company.com",     "role": "employee"},
            {"name": "Charlie Davis",   "email": "charlie@company.com", "role": "employee"},
            {"name": "Dana Lee",        "email": "dana@company.com",    "role": "employee"},
            {"name": "Evan Kim",        "email": "evan@company.com",    "role": "employee"},
            {"name": "Fiona Patel",     "email": "fiona@company.com",   "role": "employee"},
            {"name": "Grace Miller",    "email": "grace@company.com",   "role": "employee"},
        ])
        df.to_excel(USERS_FILE, index=False)

def ensure_grievance_file():
    """Ensures the grievance file exists with default data."""
    if not os.path.exists(GRIEVANCE_FILE):
        df = pd.DataFrame(
            columns=[
                "id", "title", "description", "category",
                "employee_name", "employee_email",
                "status", "assigned_to",
                "created_at", "updated_at", "comments"
            ]
        )
        # add a couple of sample rows
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        demo = [
            [1, "Office AC not working", "AC is not cooling properly in bay A3. It's affecting productivity.", "Facilities",
             "Bob Smith", "bob@company.com", "WIP", "Alice Johnson", now, now, "Technician scheduled for Friday."],
            [2, "Reimbursement delay", "Travel reimbursement for Chennai trip pending for 3 weeks, affecting personal finances.", "Finance",
             "Charlie Davis", "charlie@company.com", "Closed", "Admin Two", now, now, "Processed on 2025-09-20. Funds transferred."],
            [3, "Laptop running slow", "System is sluggish, applications freeze frequently, possibly disk issue. Need a check-up.", "IT",
             "Alice Johnson", "alice@company.com", "Open", "", now, now, ""],
            [4, "Printer in Marketing not working", "Printer on the 3rd floor (Marketing department) is showing an error and not printing.", "IT",
             "Dana Lee", "dana@company.com", "Open", "", now, now, ""],
        ]
        df = pd.concat([df, pd.DataFrame(demo, columns=df.columns)], ignore_index=True)
        df.to_excel(GRIEVANCE_FILE, index=False)

def load_users():
    """Loads user data from the Excel file."""
    ensure_users_file()
    return pd.read_excel(USERS_FILE)

@st.cache_data
def load_grievances():
    """Loads grievance data from the Excel file, using cache."""
    ensure_grievance_file()
    # Add dtype specification for 'comments' and 'assigned_to' to prevent pandas reading empty cells as float (NaN)
    return pd.read_excel(GRIEVANCE_FILE, dtype={'comments': str, 'assigned_to': str})

def save_grievances(df: pd.DataFrame):
    """Saves the DataFrame back to the Excel file and clears the cache."""
    df.to_excel(GRIEVANCE_FILE, index=False)
    load_grievances.clear() # Clear cache so next load gets fresh data

def next_id(df: pd.DataFrame) -> int:
    """Calculates the next available ID."""
    if df.empty or "id" not in df.columns:
        return 1
    return int(df["id"].max()) + 1

# -------------------------------
# Styling helpers (cards, chips)
# -------------------------------
CARD_CSS = """
<style>
/* Base Streamlit overrides */
.stApp {
    background-color: #f8f9fa; /* Light grey background for the app */
}
/* General button styling */
.stButton>button {
    width: 100%;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    transition: all 0.2s ease-in-out;
}
.stButton>button:hover {
    background-color: #f0f0f0;
    border-color: #c0c0c0;
}

/* Custom components */
.small-muted { color: #6b7280; font-size: 0.9rem; }
.kpi-card {
    border: 1px solid #eee; border-radius: 12px; padding: 15px 20px; background: #fff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 10px;
}
.kpi-title { color:#6b7280; font-weight:600; margin-bottom:6px; font-size:0.9rem; }
.kpi-value {
    display:inline-block; min-width:50px; text-align:center; font-weight:700;
    background:#eef2ff; border-radius:8px; padding:8px 12px; font-size:1.2rem;
    color: #1e40af; /* Default color for open/general */
}
.kpi-value.closed { background:#111827; color:#fff; }
.kpi-value.wip { background:#fff7ed; color:#9a3412; }
.badge {
    display:inline-block; padding:5px 10px; border-radius:999px; font-weight:600; font-size:0.8rem;
    line-height: 1; /* Adjust line height for better vertical alignment */
}
.badge-open  { background:#eef2ff; color:#1e40af; }
.badge-wip   { background:#fff7ed; color:#9a3412; }
.badge-closed{ background:#111827; color:#fff; }
.section-box {
    border: 1px solid #eee; border-radius: 12px; padding: 25px; background: #fff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 20px;
}
.hero-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 4px; }
.hero-sub    { color:#6b7280; font-size: 1rem; margin-bottom: 20px;}

/* Filter Chips with Hover */
.filter-chip-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }

/* Logout button */
.stButton.logout-button > button {
    background-color: #dc3545;
    color: white;
    font-weight: bold;
    border: none;
    padding: 8px 15px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.3s ease;
    width: auto; /* Override 100% width */
}
.stButton.logout-button > button:hover {
    background-color: #c82333;
}

/* Custom Modal styling for content INSIDE st.dialog */
.comment-history-box {
    background: #f9f9f9;
    border-radius: 8px;
    padding: 15px;
    margin-top: 15px;
    border: 1px solid #eee;
    max-height: 200px;
    overflow-y: auto;
}
.comment-entry {
    border-bottom: 1px dashed #e0e0e0;
    padding-bottom: 10px;
    margin-bottom: 10px;
}
.comment-entry:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}
.comment-meta {
    font-size: 0.85rem;
    color: #6b7280;
    margin-bottom: 5px;
}
</style>
"""

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
# Auth (super simple: email-based)
# -------------------------------
def login_ui():
    """Displays a clean login page with hero header on top and compact centered form."""
    #st.markdown(CARD_CSS, unsafe_allow_html=True)

    # --- HERO SECTION (TOP, BLUE BOX) ---
    st.markdown("""
        <div style="
            text-align: center;
            background-color: #e8f0ff;
            border-radius: 16px;
            padding: 45px 20px;
            margin: 60px auto 40px auto;
            max-width: 1500px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        ">
            <h1 style="font-weight: 800; color: #111827; margin-bottom: 10px;">
                Employee Grievance Portal
            </h1>
            <p style="color: #4b5563; font-size: 1.1rem; margin: 0;">
                Streamlined platform for employees and admins to manage grievances efficiently.
            </p>
        </div>
    """, unsafe_allow_html=True)
    

    with st.form("login_form", clear_on_submit=False):
        st.markdown("<h3 style='color:#1e3a8a; margin-bottom: 15px;'>🔐 Login</h3>", unsafe_allow_html=True)
        email = st.text_input("Email", placeholder="you@company.com")
        submitted = st.form_submit_button("Login")

    if submitted:
        users = load_users()
        row = users[users["email"].str.lower() == email.strip().lower()]
        if row.empty:
            st.error("Email not found in directory. Please contact the administrator.")
        else:
            user = row.iloc[0].to_dict()
            st.session_state.user = {"name": user["name"], "email": user["email"], "role": user["role"]}
            st.success(f"✅ Logged in as {user['name']} ({user['role']})")
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)





def logout_btn():
    """Displays the logout button."""
    # Custom CSS for placing the button at top-right
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

    # Use a container to apply the custom class for positioning
    with st.container():
        st.markdown('<div class="stButton logout-button">', unsafe_allow_html=True)
        if st.button("Logout", key="logout_button_main", help="Log out of the system", type="secondary"):
            for k in ["user", "last_filter", "emp_filter"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------
# Stats
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

# -------------------------------
# Dialog Content Function (Using st.dialog)
# -------------------------------
@st.dialog("Grievance Details")
def grievance_dialog_content(grievance_id: int):
    """Displays and handles updates for a specific grievance in a dialog."""
    df = load_grievances()
    row_data = df[df["id"] == grievance_id].iloc[0].to_dict()
    current_user_name = st.session_state.user["name"]
    current_user_email = st.session_state.user["email"]
    
    # Permissions checks
    is_admin = (st.session_state.user["role"] == "admin")
    is_creator = (row_data["employee_email"].lower() == current_user_email.lower())
    
    # An employee (creator) can comment if the ticket isn't closed
    can_employee_comment = is_creator and row_data["status"] != "Closed"
    is_editable = is_admin or can_employee_comment

    st.subheader(f"Grievance #{row_data['id']}: {row_data['title']}")
    
    # Use a form to handle state changes within the dialog effectively
    with st.form(key=f"dialog_form_{grievance_id}", clear_on_submit=False):
        st.markdown(f"**Description**: {row_data['description']}")
        st.write("")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Category**: {row_data['category']}")
            st.markdown(f"**Employee**: {row_data['employee_name']} ({row_data['employee_email']})")
        with col2:
            # Shorten the datetime string for display
            created_at = row_data['created_at'].split(' ')[0]
            updated_at = row_data['updated_at'].split(' ')[0]
            st.markdown(f"**Created At**: {created_at}")
            st.markdown(f"**Last Updated**: {updated_at}")
        st.write("")

        # Variables for update logic
        new_status = row_data["status"]
        new_assigned_to = row_data["assigned_to"]
        
        # --- Admin and Creator Action Section ---
        if is_editable:
            st.markdown("---")
            st.markdown("<h5>Update and Comment</h5>", unsafe_allow_html=True)
            
            # ADMIN ONLY FIELDS
            if is_admin:
                users = load_users()
                admin_names = users[users["role"]=="admin"]["name"].tolist()

                # Assigned To
                current_assigned = str(row_data.get("assigned_to", "")).strip()
                current_assigned = current_assigned if current_assigned in admin_names else ""
                assigned_idx = ([""] + admin_names).index(current_assigned) if current_assigned in ([""] + admin_names) else 0
                new_assigned_to = st.selectbox("Assign to", options=[""] + admin_names, index=assigned_idx, key=f"dialog_assign_{grievance_id}")

                # Status
                current_status = row_data["status"] if row_data["status"] in STATUSES else "Open"
                status_idx = STATUSES.index(current_status) if current_status in STATUSES else 0
                new_status = st.selectbox("Change Status", options=STATUSES, index=status_idx, key=f"dialog_status_{grievance_id}")
            else:
                # Employee (creator) read-only status/assignment display in this section
                st.markdown(f"**Current Status**: {status_badge(row_data['status'])}", unsafe_allow_html=True)
                st.markdown(f"**Assigned To**: {row_data['assigned_to'] or 'Not assigned'}")
            
            # COMMENT FIELD (Visible to Admin and Commenting Employee)
            new_comment = st.text_area("Add new comment", value="", key=f"dialog_new_comment_{grievance_id}", placeholder="Type your comment here...", height=80)
            
            st.markdown("---") 
            
            # Action Buttons
            if is_admin:
                btn_col1, btn_col2, btn_col3 = st.columns([0.3, 0.4, 0.3])
                save_clicked = btn_col1.form_submit_button("💾 Save Changes", type="primary")
                close_ticket_clicked = btn_col2.form_submit_button("✖ Close Ticket", type="secondary")
                btn_col3.form_submit_button("Cancel", type="secondary")
                update_needed = save_clicked or close_ticket_clicked
            
            elif can_employee_comment: # is_creator and not closed
                btn_col1, btn_col2 = st.columns([0.4, 0.6])
                # Only allow submission if a comment is entered
                save_clicked = btn_col1.form_submit_button("📝 Add Comment", type="primary", disabled=not new_comment.strip())
                btn_col2.form_submit_button("Close", type="secondary") 
                # Update needed only if the employee clicked save AND they entered a comment
                update_needed = save_clicked and new_comment.strip()
                
        # --- Read-Only View (Other employees or closed tickets) ---
        else: 
            st.markdown("---")
            st.markdown(f"**Current Status**: {status_badge(row_data['status'])}", unsafe_allow_html=True)
            st.markdown(f"**Assigned To**: {row_data['assigned_to'] or 'Not assigned'}")
            st.write("")
            st.form_submit_button("Close", type="primary") # Simply closes the dialog
            update_needed = False
            
        # --- Submission Logic ---
        if update_needed:
            idx = df.index[df["id"] == grievance_id][0]
            
            # Update Admin fields
            if is_admin:
                df.at[idx, "assigned_to"] = new_assigned_to
                df.at[idx, "status"] = new_status
                if close_ticket_clicked:
                    df.at[idx, "status"] = "Closed"

            # Add Comment logic (applies to admin and commenting employee)
            if new_comment.strip():
                existing_comments = str(df.at[idx, "comments"] or "").strip()
                comment_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {current_user_name}: {new_comment.strip()}"
                
                # Check if the existing comments are not empty before prepending a newline
                if existing_comments:
                    df.at[idx, "comments"] = f"{existing_comments}\n{comment_line}".strip()
                else:
                     df.at[idx, "comments"] = comment_line.strip()
                
            # Update timestamp
            df.at[idx, "updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_grievances(df)
            st.success("Grievance updated/comment added successfully. Refreshing view...")
            st.rerun() 

        # --- Comment History (visible to all) ---
        st.markdown("---")
        st.markdown("<h5>Comment History</h5>", unsafe_allow_html=True)
        
        comments_content = str(row_data.get("comments", "")).strip()

        if comments_content:
            st.markdown('<div class="comment-history-box">', unsafe_allow_html=True)
            comments_list = [c.strip() for c in comments_content.split('\n') if c.strip()]
            for comment in comments_list:
                st.markdown(f'<div class="comment-entry"><p>{comment}</p></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No comments yet.")


# -------------------------------
# Admin View
# -------------------------------
def admin_view():
    """Displays the admin dashboard."""
    user = st.session_state.user
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    logout_btn() # Placed at the top right

    # Header
    col_title, col_user_info = st.columns([0.7, 0.3])
    with col_title:
        st.markdown('<div class="hero-title">Employee Grievance Portal (Admin)</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-sub">Manage, track, and resolve all grievances.</div>', unsafe_allow_html=True)
    with col_user_info:
        st.markdown(f'<p class="small-muted" style="text-align:right;">Logged in as <b>{user["name"]}</b> ({user["role"]})</p>', unsafe_allow_html=True)

    df = load_grievances()

    # Stats
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Dashboard Stats")
    stats_kpis(df)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("All Grievances")

    # Filter chips
    # Initialize filter if not set
    if "last_filter" not in st.session_state:
        st.session_state.last_filter = "All"
    status_filter = st.session_state.last_filter
    
    st.markdown('<div class="filter-chip-container">', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, label in enumerate(["All", "Open", "WIP", "Closed"]):
        with cols[i]:
            button_type = "primary" if status_filter == label else "secondary"
            # Use a fixed key and set session state directly in on_click
            if st.button(label, key=f"tab_{label}", help=f"Filter by {label} status", use_container_width=True,
                         on_click=lambda l=label: st.session_state.__setitem__("last_filter", l),
                         type=button_type):
                pass
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Search
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
                    for c in ["title", "description", "employee_name", "employee_email", "category", "assigned_to", "status"]
                ),
                axis=1,
            )
        ]

    if filtered.empty:
        st.info("No grievances match the filter.")
    else:
        filtered_for_display = filtered.copy()
        # Add Status badge for rendering
        filtered_for_display["Status"] = filtered_for_display["status"].apply(status_badge)
        
        # Sort by ID descending (latest first)
        sorted_df = filtered_for_display.sort_values("id", ascending=False)
        
        # Render header row
        header_cols = st.columns([0.05, 0.25, 0.15, 0.15, 0.15, 0.1, 0.1, 0.05])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Title**")
        header_cols[2].markdown("**Category**")
        header_cols[3].markdown("**Employee**")
        header_cols[4].markdown("**Assigned To**")
        header_cols[5].markdown("**Status**")
        header_cols[6].markdown("**Created At**")
        header_cols[7].markdown("**View**")
        st.markdown("---")

        # Render data rows
        for _, row in sorted_df.iterrows():
            row_cols = st.columns([0.05, 0.25, 0.15, 0.15, 0.15, 0.1, 0.1, 0.05])
            row_cols[0].write(row["id"])
            row_cols[1].write(row["title"])
            row_cols[2].write(row["category"])
            row_cols[3].write(row["employee_name"])
            row_cols[4].write(row["assigned_to"] or "Unassigned")
            row_cols[5].markdown(row["Status"], unsafe_allow_html=True)
            
            # Display date only
            row_cols[6].write(row["created_at"].split(' ')[0])
            
            # "View" button using st.dialog
            with row_cols[7]:
                st.button("👁️", key=f"view_admin_{row['id']}", help="View Details", type="secondary",
                          on_click=lambda id=row['id']: grievance_dialog_content(id))
            st.markdown("---")


    st.markdown('</div>', unsafe_allow_html=True)

    # Download current workbook
    st.write("")
    buf = io.BytesIO()
    load_grievances().to_excel(buf, index=False)
    buf.seek(0)
    


# -------------------------------
# Employee View
# -------------------------------
def employee_view():
    """Displays the employee view, allowing submission and tracking of their own tickets."""
    user = st.session_state.user
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    logout_btn() # Placed at the top right

    # Header
    col_title, col_user_info = st.columns([0.7, 0.3])
    with col_title:
        st.markdown('<div class="hero-title">Employee Grievance Portal</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-sub">Raise, track, and resolve your grievances.</div>', unsafe_allow_html=True)
    with col_user_info:
        st.markdown(f'<p class="small-muted" style="text-align:right;">Logged in as <b>{user["name"]}</b> ({user["role"]})</p>', unsafe_allow_html=True)

    df = load_grievances()
    mine = df[df["employee_email"].str.lower() == user["email"].lower()]

    # Stats (for this employee only)
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Your Grievance Stats")
    stats_kpis(mine)
    st.markdown('</div>', unsafe_allow_html=True)

    # Raise new grievance
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Raise a New Grievance")
    with st.form("raise_grievance"):
        title = st.text_input("Title", placeholder="Brief issue summary", max_chars=100)
        desc = st.text_area("Description", placeholder="Describe the issue and context in detail. Include any relevant steps or observations.")
        category = st.selectbox("Category", options=CATEGORIES, index=0)
        
        st.markdown('<div style="text-align:right; margin-top:15px;">', unsafe_allow_html=True)
        submitted = st.form_submit_button("Submit Grievance", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        if not title.strip():
            st.error("Please enter a title.")
        else:
            gdf = load_grievances()
            rid = next_id(gdf)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "id": rid,
                "title": title.strip(),
                "description": desc.strip(),
                "category": category,
                "employee_name": user["name"],
                "employee_email": user["email"],
                "status": "Open",
                "assigned_to": "",
                "created_at": now,
                "updated_at": now,
                "comments": "",
            }
            # Use DataFrame.iloc[] to maintain column order consistency
            new_df_row = pd.DataFrame([new_row], columns=gdf.columns)
            gdf = pd.concat([gdf, new_df_row], ignore_index=True)
            save_grievances(gdf)
            st.success(f"Grievance #{rid} submitted successfully. You can track its status below.")
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # List my grievances
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


    q = st.text_input("Search by title, description, category", key="emp_search_query", placeholder="Search your tickets...")
    filtered = mine.copy()
    if filter_status != "All":
        filtered = filtered[filtered["status"]==filter_status]
    if q:
        ql = q.lower()
        filtered = filtered[
            filtered.apply(
                lambda r: any(ql in str(r[c]).lower() for c in ["title","description","category","status","assigned_to"]),
                axis=1
            )
        ]
        
    if filtered.empty:
        st.info("You haven't submitted any grievances yet or none match the filter.")
    else:
        # Pre-process status column with HTML badges
        filtered_for_display = filtered.copy()
        filtered_for_display["Status"] = filtered_for_display["status"].apply(status_badge)
        
        # Sort by ID descending (latest first)
        sorted_df = filtered_for_display.sort_values("id", ascending=False)
        
        # Render header row
        # Adjusted columns for employee view to remove employee name column which is redundant
        header_cols = st.columns([0.05, 0.3, 0.15, 0.15, 0.1, 0.1, 0.05]) 
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Title**")
        header_cols[2].markdown("**Category**")
        header_cols[3].markdown("**Assigned To**")
        header_cols[4].markdown("**Status**")
        header_cols[5].markdown("**Created At**")
        header_cols[6].markdown("**View**")
        st.markdown("---")

        # Render data rows
        for _, row in sorted_df.iterrows():
            row_cols = st.columns([0.05, 0.3, 0.15, 0.15, 0.1, 0.1, 0.05])
            row_cols[0].write(row["id"])
            row_cols[1].write(row["title"])
            row_cols[2].write(row["category"])
            row_cols[3].write(row["assigned_to"] or "Unassigned")
            row_cols[4].markdown(row["Status"], unsafe_allow_html=True)
            
            # Display date only
            row_cols[5].write(row["created_at"].split(' ')[0])
            
            # "View" button for st.dialog
            with row_cols[6]:
                st.button("👁️", key=f"view_employee_{row['id']}", help="View Details", type="secondary",
                          on_click=lambda id=row['id']: grievance_dialog_content(id))
            st.markdown("---")


    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------
# App Entrypoint
# -------------------------------
st.set_page_config(page_title="Employee Grievance Portal", layout="wide", initial_sidebar_state="collapsed")

st.markdown(CARD_CSS, unsafe_allow_html=True)

if "user" not in st.session_state:
    login_ui()
else:
    role = st.session_state.user["role"]
    
    if role == "admin":
        admin_view()
    else:
        employee_view()
