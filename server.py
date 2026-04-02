from flask import Flask, request, jsonify, send_from_directory
import os
import cv2
import pytesseract
import sqlite3
import re
from datetime import datetime
import platform

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
DB_FILE = "accounting.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------------------------
# TESSERACT CONFIG
# ------------------------------------

import shutil

tesseract_path = shutil.which("tesseract")

if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

# ------------------------------------
# DATABASE
# ------------------------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            month TEXT,
            type TEXT,
            client TEXT,
            invoice TEXT,
            category TEXT,
            subtotal REAL,
            tax REAL,
            total REAL
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ------------------------------------
# IMAGE PREPROCESSING
# ------------------------------------

def preprocess_image(path):

  img = cv2.resize(img, (800, 1000))

    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.GaussianBlur(gray, (5,5), 0)

    gray = cv2.adaptiveThreshold(
        gray,255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,2
    )

    return gray

# ------------------------------------
# OCR
# ------------------------------------

def read_text(path):

    processed = preprocess_image(path)

    if processed is None:
        return ""

    text = pytesseract.image_to_string(processed)
    return text.lower()

# ------------------------------------
# DATA EXTRACTION
# ------------------------------------

def extract_data(text):

    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client": "",
        "invoice": "",
        "subtotal": 0,
        "tax": 0,
        "total": 0
    }

    total = re.findall(r"\d+\.\d{2}", text)

    if total:
        data["total"] = max([float(x) for x in total])

    inv = re.search(r"(invoice|inv|bill)\s*#?\s*(\w+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    return data

# ------------------------------------
# SAVE RECORD
# ------------------------------------

def save_record(data, record_type, text):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    month = datetime.now().strftime("%Y-%m")

    c.execute("""
        INSERT INTO records (date, month, type, client, invoice, category, subtotal, tax, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["date"],
        month,
        record_type,
        data["client"],
        data["invoice"],
        "Expense",
        data["subtotal"],
        data["tax"],
        data["total"]
    ))

    conn.commit()
    conn.close()

# ------------------------------------
# TOTALS
# ------------------------------------

def get_totals():

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT SUM(total) FROM records WHERE type='Income'")
    income = c.fetchone()[0] or 0

    c.execute("SELECT SUM(total) FROM records WHERE type='Expense'")
    expenses = c.fetchone()[0] or 0

    conn.close()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ------------------------------------
# PROCESS FILE
# ------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    file = request.files["file"]

    filename = "upload.jpg"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    text = read_text(path)
    data = extract_data(text)

    if data["total"] == 0:
        income, expenses, profit, annual = get_totals()
        return jsonify({
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "annual": annual
        })

    if "deposit" in text or "payment received" in text:
        save_record(data, "Income", text)
    else:
        save_record(data, "Expense", text)

    income, expenses, profit, annual = get_totals()

    return jsonify({
        "income": income,
        "expenses": expenses,
        "profit": profit,
        "annual": annual
    })

# ------------------------------------
# MONTHLY REPORT (for charts)
# ------------------------------------

@app.route("/monthly-report")
def monthly():

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT month, SUM(total)
        FROM records
        GROUP BY month
        ORDER BY month
    """)

    rows = c.fetchall()
    conn.close()

    data = []

    for r in rows:
        data.append({
            "Month": r[0],
            "Amount": r[1]
        })

    return jsonify(data)

# ------------------------------------
# HOME
# ------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ------------------------------------
# RUN
# ------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
