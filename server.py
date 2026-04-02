from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
import re
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
DB_FILE = "accounting.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------------------
# DATABASE
# ---------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            client TEXT,
            invoice TEXT,
            total REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------------------
# EXTRACT SIMPLE DATA
# ---------------------------

def extract_data(text):

    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client": "Unknown",
        "invoice": "",
        "total": 0
    }

    amounts = re.findall(r"\d+\.\d{2}", text)

    if amounts:
        data["total"] = max([float(x) for x in amounts])

    inv = re.search(r"(invoice|inv)\s*#?\s*(\w+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    return data

# ---------------------------
# SAVE
# ---------------------------

def save(data, type_):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO records (date, type, client, invoice, total)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["date"],
        type_,
        data["client"],
        data["invoice"],
        data["total"]
    ))

    conn.commit()
    conn.close()

# ---------------------------
# TOTALS
# ---------------------------

def totals():

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT SUM(total) FROM records WHERE type='Income'")
    income = c.fetchone()[0] or 0

    c.execute("SELECT SUM(total) FROM records WHERE type='Expense'")
    expenses = c.fetchone()[0] or 0

    conn.close()

    profit = income - expenses

    return income, expenses, profit, profit*12

# ---------------------------
# PROCESS
# ---------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    file = request.files.get("file")

    if not file:
        return jsonify({"error": "no file"}), 400

    text = file.read().decode("utf-8", errors="ignore").lower()

    data = extract_data(text)

    if data["total"] == 0:
        return jsonify(dict(zip(
            ["income","expenses","profit","annual"],
            totals()
        )))

    if "deposit" in text:
        save(data, "Income")
    else:
        save(data, "Expense")

    return jsonify(dict(zip(
        ["income","expenses","profit","annual"],
        totals()
    )))

# ---------------------------
# HOME
# ---------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ---------------------------
# RUN
# ---------------------------

if __name__ == "__main__":
    app.run()
