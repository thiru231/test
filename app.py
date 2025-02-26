import os
import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Attempt MySQL Connection
try:
    conn = mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        connect_timeout=10  # Optional: Set timeout to prevent long waits
    )
    st.success("✅ Connected to MySQL successfully!")
except mysql.connector.Error as err:
    st.error(f"❌ Database connection failed: {err}")
    st.stop()  # Prevent further execution if connection fails
cursor = conn.cursor()

# Function to check user login
def check_login(email, password):
    cursor.execute("SELECT user_name, role, id FROM users WHERE email=%s AND password=%s", (email, password))
    return cursor.fetchone()

# Login Page
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = None
    st.session_state.user_role = None
    st.session_state.user_id = None

if not st.session_state.logged_in:
    st.title("🔐 Login Page")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = check_login(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user[0]
            st.session_state.user_role = user[1]
            st.session_state.user_id = user[2]
            st.success(f"✅ Welcome, {user[0]}! You are logged in as {user[1]}.")
            st.rerun()
        else:
            st.error("❌ Invalid Email or Password. Please try again.")
    st.stop()

# Logout Button
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user_name = None
    st.session_state.user_role = None
    st.session_state.user_id = None
    st.rerun()

# Streamlit App Title
st.title("Task Management System")

# Sidebar Navigation
menu_options = ["Add Team", "Add Task", "View Data", "Dashboard"]
if st.session_state.user_role == "admin":
    menu_options = ["Add User", "Add Team", "Add Task", "View Data", "Dashboard"]

menu = st.sidebar.radio("Menu", menu_options)

# Add User (Only Admin)
if menu == "Add User" and st.session_state.user_role == "admin":
    st.subheader("Add a New User")
    user_name = st.text_input("User Name")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["admin", "manager", "employee"])
    
    if st.button("Add User"):
        cursor.execute("INSERT INTO users (user_name, name, email, password, role) VALUES (%s, %s, %s, %s, %s)",
                       (user_name, name, email, password, role))
        conn.commit()
        st.success("User added successfully!")

# Add Team 
elif menu == "Add Team" and st.session_state.user_role in ["admin", "employee"]:
    st.subheader("Add a New Team")
    team_name = st.text_input("Team Name")
    
    if st.button("Add Team"):
        cursor.execute("INSERT INTO teams (team_name) VALUES (%s)", (team_name,))
        conn.commit()
        st.success("Team added successfully!")

# Add Task 
elif menu == "Add Task" and st.session_state.user_role in ["admin", "employee"]:
    st.subheader("Add a New Task")
    task_name = st.text_input("Task Name")
    time_frame = st.text_input("Time Frame (e.g., 2 hours, 1 day)")
    date = st.date_input("Task Date")
    
    cursor.execute("SELECT id, user_name FROM users")
    users = cursor.fetchall()
    user_dict = {user[1]: user[0] for user in users}
    user_id = st.selectbox("Assign to User", list(user_dict.keys()))
    
    cursor.execute("SELECT id, team_name FROM teams")
    teams = cursor.fetchall()
    team_dict = {team[1]: team[0] for team in teams}
    team_id = st.selectbox("Assign to Team", list(team_dict.keys()))
    
    if st.button("Add Task"):
        cursor.execute("INSERT INTO tasks (task_name, time_frame, date, user_id, team_id) VALUES (%s, %s, %s, %s, %s)",
                       (task_name, time_frame, date, user_dict[user_id], team_dict[team_id]))
        conn.commit()
        st.success("Task added successfully!")

# View Data
elif menu == "View Data":
    st.subheader("View Stored Data")
    
    current_year = datetime.now().year
    year_start = datetime(current_year, 1, 1)
    year_end = datetime(current_year, 12, 31, 23, 59, 59)
    start_date = st.date_input("Start Date", year_start)
    end_date = st.date_input("End Date", year_end)
    
    if st.session_state.user_role == "admin":
        user_filter = st.text_input("Filter by User Name (Optional)")
        query = "SELECT tasks.task_name, tasks.time_frame, tasks.date, teams.team_name, users.user_name FROM tasks LEFT JOIN users ON users.id = tasks.user_id LEFT JOIN teams ON teams.id = tasks.team_id WHERE tasks.date BETWEEN %s AND %s"
        params = (start_date, end_date)
        
        if user_filter:
            query += " AND users.user_name = %s"
            params += (user_filter,)
        
    elif st.session_state.user_role == "employee":
        query = "SELECT tasks.task_name, tasks.time_frame, tasks.date, teams.team_name FROM tasks LEFT JOIN teams ON teams.id = tasks.team_id WHERE user_id = %s AND tasks.date BETWEEN %s AND %s"
        params = (st.session_state.user_id, start_date, end_date)
        
    df = pd.read_sql(query, conn, params=params)
    st.write(df)

# 📊 Dashboard (New Section)
elif menu == "Dashboard":
    if st.session_state.user_role == "admin":
        st.title("📊 Admin Dashboard")

        # Total Employees
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='employee'")
        total_employees = cursor.fetchone()[0]
        st.metric(label="Total Employees", value=total_employees)

        # Employee Hours Chart
        query = """
        SELECT users.user_name, SUM(TIME_TO_SEC(tasks.time_frame)) / 3600 AS total_hours
        FROM tasks 
        JOIN users ON users.id = tasks.user_id 
        GROUP BY users.user_name
        """
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            fig = px.bar(df, x="user_name", y="total_hours", title="Total Hours Worked per Employee", labels={"user_name": "Employee", "total_hours": "Hours Worked"})
            st.plotly_chart(fig)
        else:
            st.warning("No data available.")

    elif st.session_state.user_role == "employee":
        st.title("📈 Employee Dashboard")

        query = """
        SELECT tasks.date, SUM(TIME_TO_SEC(tasks.time_frame)) / 3600 AS total_hours
        FROM tasks 
        WHERE user_id = %s 
        GROUP BY tasks.date
        ORDER BY tasks.date
        """
        df = pd.read_sql(query, conn, params=(st.session_state.user_id,))
        
        if not df.empty:
            fig = px.line(df, x="date", y="total_hours", title="Your Working Hours Over Time", labels={"date": "Date", "total_hours": "Hours Worked"})
            st.plotly_chart(fig)
        else:
            st.warning("No data available.")

# Close connection
cursor.close()
conn.close()
