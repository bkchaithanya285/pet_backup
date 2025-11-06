import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import smtplib
import time
import threading
import pandas as pd
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------- FIREBASE INITIALIZATION --------------------
try:
    if not firebase_admin._apps:
        # ✅ For Render (reads from environment variable)
        if os.getenv("FIREBASE_CONFIG"):
            firebase_config = json.loads(os.getenv("FIREBASE_CONFIG"))
            with open("temp_firebase_key.json", "w") as f:
                json.dump(firebase_config, f)
            cred = credentials.Certificate("temp_firebase_key.json")

        # ✅ For Local (reads from firebase_key.json file)
        else:
            cred = credentials.Certificate("firebase_key.json")

        firebase_admin.initialize_app(cred)

    db = firestore.client()
    st.success("✅ Firebase connected successfully!")
except Exception as e:
    st.error(f"❌ Firebase initialization failed: {e}")
    st.stop()

# -------------------- EMAIL FUNCTION --------------------
def send_email(to_email, subject, message):
    sender_email = "petremainder@gmail.com"
    sender_password = "gqguiecwiapumctq"  # Gmail App Password (no spaces)

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print("❌ Email sending failed:", e)

# -------------------- STREAMLIT CONFIG --------------------
st.set_page_config(page_title="Pet Vaccination Reminder", page_icon="🐾", layout="wide")
st.title("🐾 Pet Vaccination Reminder App")
st.write("Add, manage, and download your pet vaccination reminders easily.")

hours = [f"{h:02d}" for h in range(24)]
minutes = [f"{m:02d}" for m in range(60)]

# -------------------- ADD NEW REMINDER --------------------
with st.form("add_form"):
    st.subheader("➕ Add New Reminder")
    pet_name = st.text_input("🐶 Pet Name")
    vaccine_name = st.text_input("💉 Vaccine Name")
    vaccination_date = st.date_input("📅 Vaccination Date")
    reminder_date = st.date_input("📧 Reminder Email Date")

    col1, col2 = st.columns(2)
    with col1:
        selected_hour = st.selectbox("🕐 Hour (00–23)", hours)
    with col2:
        selected_minute = st.selectbox("🕑 Minute (00–59)", minutes)

    email = st.text_input("✉ Owner Email Address")
    submit = st.form_submit_button("💾 Save Reminder")

    if submit:
        if pet_name and vaccine_name and email:
            formatted_time = f"{selected_hour}:{selected_minute}"
            data = {
                "pet_name": pet_name,
                "vaccine_name": vaccine_name,
                "vaccination_date": str(vaccination_date),
                "reminder_date": str(reminder_date),
                "reminder_time": formatted_time,
                "email": email,
                "sent": False,
            }
            db.collection("schedules").add(data)
            st.success(
                f"✅ Reminder saved for {pet_name}'s vaccine on {vaccination_date}. "
                f"Email will be sent at {formatted_time} on {reminder_date}."
            )
        else:
            st.error("⚠ Please fill all fields!")

# -------------------- FETCH DATA --------------------
st.subheader("📋 Scheduled Reminders")

docs = list(db.collection("schedules").stream())
records = []
for idx, doc in enumerate(docs, start=1):
    d = doc.to_dict()
    d["id"] = doc.id
    records.append({
        "S.No": idx,
        "🐶 Pet Name": d.get("pet_name", ""),
        "💉 Vaccine Name": d.get("vaccine_name", ""),
        "📅 Vaccination Date": d.get("vaccination_date", ""),
        "📧 Owner Email": d.get("email", ""),
        "📆 Reminder Date": d.get("reminder_date", ""),
        "⏰ Reminder Time": d.get("reminder_time", ""),
        "Sent": "✅" if d.get("sent") else "❌",
        "id": doc.id
    })

# -------------------- TABLE DISPLAY --------------------
if records:
    df = pd.DataFrame(records).drop(columns=["id"])
    st.dataframe(df, use_container_width=True)

    # Download as CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download Table as CSV", data=csv, file_name="pet_reminders.csv", mime="text/csv")

    # Delete buttons beside each record
    st.subheader("🗑 Delete Individual Reminder")
    for idx, rec in enumerate(records, start=1):
        col1, col2, col3, col4 = st.columns([3, 3, 3, 1])
        with col1:
            st.write(f"{idx}. {rec['🐶 Pet Name']}")
        with col2:
            st.write(f"{rec['💉 Vaccine Name']}")
        with col3:
            st.write(f"{rec['📆 Reminder Date']} {rec['⏰ Reminder Time']}")
        with col4:
            if st.button("🗑 Delete", key=rec["id"]):
                db.collection("schedules").document(rec["id"]).delete()
                st.success(f"✅ Deleted reminder for {rec['🐶 Pet Name']}. Please refresh.")
else:
    st.info("No reminders scheduled yet. Add one above to get started!")

# -------------------- CLEAR ALL BUTTON --------------------
if st.button("🧹 Clear All Reminders"):
    for doc in docs:
        db.collection("schedules").document(doc.id).delete()
    st.warning("🗑 All reminders deleted successfully! Refresh to update.")

# -------------------- EMAIL SCHEDULER --------------------
def check_and_send_emails():
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")

    docs = db.collection("schedules").where("sent", "==", False).stream()
    for doc in docs:
        data = doc.to_dict()
        if data.get("reminder_date") == current_date and data.get("reminder_time") == current_time:
            subject = f"🐶 Reminder: {data['pet_name']}'s Vaccination is on {data['vaccination_date']}"
            message = (
                f"Hello! 👋\n\nThis is a reminder for your pet's vaccination.\n\n"
                f"🐾 Pet Name: {data['pet_name']}\n"
                f"💉 Vaccine: {data['vaccine_name']}\n"
                f"📅 Vaccination Date: {data['vaccination_date']}\n"
                f"⏰ Reminder Time: {data['reminder_time']} on {data['reminder_date']}\n\n"
                f"Take care of your pet! ❤"
            )
            try:
                send_email(data["email"], subject, message)
                db.collection("schedules").document(doc.id).update({"sent": True})
            except Exception as e:
                print("❌ Email send failed:", e)

# -------------------- BACKGROUND SCHEDULER --------------------
def run_scheduler():
    while True:
        check_and_send_emails()
        time.sleep(60)

threading.Thread(target=run_scheduler, daemon=True).start()
