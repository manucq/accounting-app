from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
import re
from datetime import datetime
import pdfplumber
from PIL import Image
import requests

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
# OCR (API GRATIS)
# ---------------------------

def ocr_image(file):

    API_KEY = "K82953514288957"  # 👈 PON TU KEY AQUÍ

    response = requests.post(
        "https://api.ocr.space/parse/image",
        files={"file": file},
        data={
            "apikey": API_KEY,
            "language": "eng"
        },
    )

    result = response.json()

    try:
        return result["ParsedResults"][0]["ParsedText"].lower()
    except:
        return ""

# ---------------------------
# READ FILE
# ---------------------------

def read_file(file, filename):

    if filename.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text.lower()

    else:
        return ocr_image(file)

# ---------------------------
# EXTRACT DATA
# ---------------------------

def extract_data(text):

    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client": "Unknown",
        "invoice": "",
        "total": 0
    }

    # TOTAL
    amounts = re.findall(r"\d+\.\d{2}", text)
    if amounts:
        data["total"] = max([float(x) for x in amounts])

    # INVOICE
    inv = re.search(r"(invoice|inv|bill)\s*#?\s*(\w+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    # CLIENT (línea válida)
    lines = text.split("\n")
    for line in lines[:10]:
        line = line.strip()
        if len(line) > 4 and len(line) < 40:
            if not any(x in line for x in ["invoice","total","date"]):
                data["client"] = line.title()
                break

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

    return income, expenses, profit, profit * 12

# ---------------------------
# PROCESS FILE
# ---------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    try:
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "no file"}), 400

        filename = file.filename.lower()

        text = read_file(file, filename)

        data = extract_data(text)

        if data["total"] == 0:
            return jsonify(dict(zip(
                ["income","expenses","profit","annual"],
                totals()
            )))

        if "deposit" in text or "payment" in text:
            save(data, "Income")
        else:
            save(data, "Expense")

        return jsonify(dict(zip(
            ["income","expenses","profit","annual"],
            totals()
        )))

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

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
