# hoscon_app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, UTC
import json, os

DB_PATH = "hoscon_demo.db"

# --- DB utilities ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        status TEXT,
        notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY,
        name TEXT,
        role TEXT,
        department_id INTEGER,
        present INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY,
        type TEXT,
        description TEXT,
        timestamp TEXT,
        priority TEXT,
        status TEXT DEFAULT 'Open'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        incident_id INTEGER,
        title TEXT,
        assigned_to INTEGER,
        status TEXT,
        timestamp TEXT,
        resource_id INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        quantity INTEGER,
        unit TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS communication_logs (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        sender TEXT,
        recipient TEXT,
        message TEXT,
        incident_id INTEGER
    )""")


    conn.commit()
    return conn

conn = init_db()

# --- Sample Data Insertion ---
def insert_sample_data(conn):
    c = conn.cursor()

    # Sample data for departments
    sample_departments = [
        ('Emergency Department', 'Green', 'All clear'),
        ('Intensive Care Unit (ICU)', 'Green', 'Normal operations'),
        ('Surgery', 'Green', 'Scheduled procedures'),
        ('Pharmacy', 'Green', 'Well-stocked'),
    ]
    c.executemany("INSERT OR IGNORE INTO departments (name, status, notes) VALUES (?, ?, ?)", sample_departments)

    # Sample data for staff (assuming department IDs will be assigned automatically starting from 1 if inserted first)
    # We need to get the department IDs after inserting departments
    dept_ids = {row[1]: row[0] for row in c.execute("SELECT id, name FROM departments").fetchall()}

    sample_staff = [
        ('Alice Smith', 'Nurse', dept_ids.get('Emergency Department'), 1),
        ('Bob Johnson', 'Doctor', dept_ids.get('Intensive Care Unit (ICU)'), 1),
        ('Charlie Brown', 'Surgeon', dept_ids.get('Surgery'), 0),
        ('Diana Prince', 'Pharmacist', dept_ids.get('Pharmacy'), 1),
    ]
    c.executemany("INSERT OR IGNORE INTO staff (name, role, department_id, present) VALUES (?, ?, ?, ?)", sample_staff)

    # Sample data for incidents
    sample_incidents = [
        ('Mass Casualty Event', 'Multiple casualties arriving from highway accident', datetime.now(UTC).isoformat(), 'Critical', 'Open'),
        ('Power Outage', 'Hospital lost main power, on backup generator', datetime.now(UTC).isoformat(), 'High', 'In Progress'),
        ('Supply Shortage', 'Running low on sterile gloves in Emergency', datetime.now(UTC).isoformat(), 'Medium', 'Open'),
        ('Staffing Issue', 'Shortage of nurses in ICU for night shift', datetime.now(UTC).isoformat(), 'High', 'Open'),
    ]
    c.executemany("INSERT INTO incidents (type, description, timestamp, priority, status) VALUES (?, ?, ?, ?, ?)", sample_incidents)

    # Sample data for resources
    sample_resources = [
        ('Ventilator', 10, 'units'),
        ('Sterile Gloves', 500, 'pairs'),
        ('Blood Bags (O+)', 20, 'units'),
        ('Stretchers', 15, 'units'),
    ]
    c.executemany("INSERT OR IGNORE INTO resources (name, quantity, unit) VALUES (?, ?, ?)", sample_resources)

    conn.commit()
    print("Sample data added to the database.")

# Insert sample data when the app starts (optional, you might want to do this once)
insert_sample_data(conn)


def query_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

def update_incident_details(incident_id, incident_type, description, priority, status):
    """Updates the details of a selected incident in the database."""
    try:
        c = conn.cursor()
        c.execute("""UPDATE incidents SET type=?, description=?, priority=?, status=?
                     WHERE id=?""",
                  (incident_type, description, priority, status, incident_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating incident: {e}")
        return False


# --- Export ---
def export_all():
    os.makedirs("exports", exist_ok=True)
    bundle = {}
    for t in ["departments","staff","incidents","tasks", "resources", "communication_logs"]:
        df = query_df(f"SELECT * FROM {t}")
        df.to_csv(f"exports/{t}.csv", index=False)
        bundle[t] = df.to_dict(orient="records")
    with open("exports/bundle.json","w") as f:
        json.dump(bundle, f, indent=2)
    return os.listdir("exports")

# --- UI ---
st.title("🏥 HOSCON – Hospital Situational Control")
st.write("""
HOSCON is a Hospital Situational Control application designed to enhance awareness and management during critical situations.
Key Features:
- **Department Status Monitoring**: Track the operational status (Green, Yellow, Red) and add notes for each hospital department.
- **Staff Muster**: Manage staff details, roles, and check-in status to monitor personnel availability.
- **Incident Logging & Tracking**: Record and track incidents with details including type, description, timestamp, priority level, and status (Open, In Progress, Resolved).
- **Task Assignment & Follow-up**: Assign tasks related to incidents to staff members and monitor their progress.
- **Resource Availability Dashboard**: Monitor the availability of critical resources such as beds, medical supplies, and equipment.
- **Data Export**: Export all application data to CSV and JSON formats for reporting and analysis.
""") # Updated with a more detailed description
st.write("Author: Kate Abonyo (winsletkate210@gmail.com)")

# Removed "Staff Muster" from the tabs list and added "Resources" and "Export"
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Dashboard", "Staff Muster", "Role & Tasks", "Incidents", "Resources", "Export"])

with tab1:
    st.subheader("Department Status")
    df = query_df("SELECT * FROM departments")
    st.dataframe(df)

    dept_names = df["name"].tolist() if not df.empty else []
    selected_dept = st.selectbox("Select Department", dept_names)

    if selected_dept:
        current_dept_info = df[df["name"] == selected_dept].iloc[0]
        initial_status = current_dept_info["status"] if pd.notna(current_dept_info["status"]) else "Green"
        initial_notes = current_dept_info["notes"] if pd.notna(current_dept_info["notes"]) else ""

        status = st.radio("Status", ["Green","Yellow","Red"], index=["Green","Yellow","Red"].index(initial_status))
        notes = st.text_area("Notes", value=initial_notes)

        if st.button("Update Department Status"): # Changed button label for clarity
            conn.execute("UPDATE departments SET status=?, notes=? WHERE name=?",
                         (status, notes, selected_dept))
            conn.commit()
            st.success("Updated!")
            st.dataframe(query_df("SELECT * FROM departments"))
    else:
        st.info("Add departments to update their status.")


with tab2:
    st.subheader("Staff Management")

    st.subheader("Register New Staff")
    new_staff_name = st.text_input("New Staff Name")
    new_staff_role = st.text_input("New Staff Role")
    dept_list = query_df("SELECT * FROM departments")
    dept_options = [(row['name'], row['id']) for index, row in dept_list.iterrows()] if not dept_list.empty else []

    if dept_options: # Add this check
        new_staff_dept_id = st.selectbox("New Staff Department", options=dept_options, format_func=lambda x: x[0] if isinstance(x, tuple) else x)

        if st.button("Add New Staff"):
            if new_staff_name and new_staff_role and new_staff_dept_id:
                try:
                    conn.execute("INSERT INTO staff(name, role, department_id, present) VALUES (?, ?, ?, ?)",
                                 (new_staff_name, new_staff_role, new_staff_dept_id[1], 0)) # Use the ID from the tuple
                    conn.commit()
                    st.success(f"Staff member {new_staff_name} added.")
                except sqlite3.IntegrityError:
                    st.error(f"Staff member {new_staff_name} already exists.")
            else:
                st.warning("Please fill in all fields to add new staff.")
    else:
        st.info("Please add departments first to register staff.") # Add this message

    st.subheader("Update Existing Staff Status")
    staff = query_df("SELECT * FROM staff")
    staff_names = staff["name"].tolist() if not staff.empty else []

    if staff_names and dept_options: # Add this check
        staff_to_update_name = st.selectbox("Select Staff to Update", staff_names)

        if staff_to_update_name:
            current_staff_info = staff[staff["name"] == staff_to_update_name].iloc[0]
            updated_role = st.text_input("Role", value=current_staff_info["role"])

            # Revised logic to find the correct index for the department selectbox
            current_dept_id = current_staff_info["department_id"]
            current_dept_index = 0 # Default to the first option
            for index, (name, dept_id) in enumerate(dept_options):
                if dept_id == current_dept_id:
                    current_dept_index = index
                    break
            else:
                 st.warning(f"Department ID {current_dept_id} for staff {staff_to_update_name} not found in current department options. Defaulting to first department.")


            updated_dept_id = st.selectbox("Department", options=dept_options, index=current_dept_index, format_func=lambda x: x[0] if isinstance(x, tuple) else x)
            updated_present = st.checkbox("Present?", value=bool(current_staff_info["present"]))

            if st.button("Update Staff Details"):
                staff_id_to_update = current_staff_info["id"]
                conn.execute("UPDATE staff SET role=?, department_id=?, present=? WHERE id=?",
                             (updated_role, updated_dept_id[1], int(updated_present), staff_id_to_update)) # Use the ID from the tuple
                conn.commit()
                st.success(f"Staff member {staff_to_update_name} updated.")
    elif staff_names and not dept_options:
        st.info("Please add departments first to update staff details.")
    else:
        st.info("No staff available to update. Please register new staff first.")


    st.subheader("Present Staff")
    present_staff_df = query_df("SELECT s.name, s.role, d.name as department FROM staff s JOIN departments d ON s.department_id = d.id WHERE s.present = 1")
    st.dataframe(present_staff_df)

    st.subheader("All Staff")
    all_staff_df = query_df("SELECT s.name, s.role, d.name as department, s.present FROM staff s JOIN departments d ON s.department_id = d.id")
    st.dataframe(all_staff_df)


with tab3:
    st.subheader("Assign Roles / Create Tasks")
    staff = query_df("SELECT * FROM staff")
    staff_options = [(row['name'], row['id']) for index, row in staff.iterrows()] if not staff.empty else []

    if staff_options: # Add this check
        staff_to_assign = st.selectbox("Assign To", options=staff_options, format_func=lambda x: x[0] if isinstance(x, tuple) else x)

        inc_type = st.text_input("Incident Type")
        inc_desc = st.text_area("Incident Description")
        inc_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"]) # Added priority selectbox
        inc_status = st.selectbox("Incident Status", ["Open", "In Progress", "Resolved"]) # Added status selectbox
        initial_task_title = st.text_input("Initial Task Title", value="Initial Response") # Added input for initial task title

        if st.button("Log Incident and Assign Task"): # Changed button label
            if inc_type and inc_desc and staff_to_assign:
                ts = datetime.now(UTC).isoformat()
                conn.execute("INSERT INTO incidents(type,description,timestamp,priority,status) VALUES (?,?,?,?,?)", # Updated insert statement
                             (inc_type, inc_desc, ts, inc_priority, inc_status)) # Updated values
                inc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                conn.execute("INSERT INTO tasks(incident_id,title,assigned_to,status,timestamp) VALUES (?,?,?,?,?)",
                             (inc_id, initial_task_title, # Used the input task title
                              staff_to_assign[1], # Use the staff ID from the tuple
                              "Open", ts))
                conn.commit()
                st.success("Incident logged and initial task assigned.") # Updated success message
            else:
                st.warning("Please fill in Incident Type, Description, and select staff to assign.")
    else:
        st.info("Please add staff first to log incidents and assign tasks.") # Add this message


with tab4:
    st.subheader("Incidents & Tasks")
    incidents_df = query_df("SELECT * FROM incidents")
    st.subheader("Incidents")
    st.dataframe(incidents_df)

    tasks_df = query_df("SELECT t.*, s.name as assigned_staff FROM tasks t LEFT JOIN staff s ON t.assigned_to = s.id")
    st.subheader("Tasks")
    st.dataframe(tasks_df)

    if not tasks_df.empty:
        task_options = [(f"{row['title']} (ID: {row['id']})", row['id']) for index, row in tasks_df.iterrows()]
        task_to_update_tuple = st.selectbox("Select Task to Update", options=task_options, format_func=lambda x: x[0] if isinstance(x, tuple) else x)

        if task_to_update_tuple:
            task_to_update_id = task_to_update_tuple[1]
            current_task_info = tasks_df[tasks_df["id"] == task_to_update_id].iloc[0]
            initial_task_status = current_task_info["status"] if pd.notna(current_task_info["status"]) else "Open"
            new_status = st.radio("Update Status", ["Open","In Progress","Completed"], index=["Open","In Progress","Completed"].index(initial_task_status))

            if st.button("Update Task Status"):
                conn.execute("UPDATE tasks SET status=?, timestamp=? WHERE id=?",
                             (new_status, datetime.now(UTC).isoformat(), task_to_update_id))
                conn.commit()
                st.success("Task updated.")
                # Refresh tasks display
                tasks_df_updated = query_df("SELECT t.*, s.name as assigned_staff FROM tasks t LEFT JOIN staff s ON t.assigned_to = s.id")
                st.subheader("Tasks (Updated)")
                st.dataframe(tasks_df_updated)
    else:
        st.info("No tasks available to update.")


with tab5: # This is now the "Resources" tab
    st.subheader("Resource Availability")

    st.subheader("Add New Resource")
    new_resource_name = st.text_input("Resource Name")
    new_resource_quantity = st.number_input("Quantity", min_value=0, step=1)
    new_resource_unit = st.text_input("Unit (e.g., beds, cylinders)")
    if st.button("Add Resource"):
        if new_resource_name and new_resource_quantity is not None and new_resource_unit:
            try:
                conn.execute("INSERT INTO resources(name, quantity, unit) VALUES (?, ?, ?)",
                             (new_resource_name, new_resource_quantity, new_resource_unit))
                conn.commit()
                st.success(f"Resource '{new_resource_name}' added.")
            except sqlite3.IntegrityError:
                st.error(f"Resource '{new_resource_name}' already exists.")
        else:
            st.warning("Please fill in all fields to add a new resource.")

    st.subheader("Update Resource Quantity")
    resources_df = query_df("SELECT * FROM resources")
    resource_names = resources_df["name"].tolist() if not resources_df.empty else []
    resource_to_update_name = st.selectbox("Select Resource to Update", resource_names)

    if resource_to_update_name:
        current_resource_info = resources_df[resources_df["name"] == resource_to_update_name].iloc[0]
        updated_quantity = st.number_input("New Quantity", min_value=0, step=1, value=int(current_resource_info["quantity"]))
        if st.button("Update Quantity"):
            resource_id_to_update = current_resource_info["id"]
            conn.execute("UPDATE resources SET quantity=? WHERE id=?",
                         (updated_quantity, resource_id_to_update))
            conn.commit()
            st.success(f"Quantity for '{resource_to_update_name}' updated.")

    st.subheader("Current Resource Levels")
    st.dataframe(query_df("SELECT * FROM resources"))


with tab6: # This is now the "Export" tab
    st.subheader("Export Data")
    if st.button("Export to CSV + JSON"):
        files = export_all()
        st.write("Exported files:", files)
        st.info("Use the file browser to download from the `exports/` folder.")