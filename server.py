from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
import re
from datetime import datetime
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

    # CLIENT (primer texto válido)
    lines = text.split("\n")
    for line in lines[:10]:
        line = line.strip()
        if len(line) > 4 and not any(x in line for x in ["invoice","total","date","tax"]):
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

    return income, expenses, profit, profit*12

# ---------------------------
# PROCESS FILE (OCR REAL)
# ---------------------------

@app.route("/process-file", methods=["POST"])
def process_file():
    try:
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file"}), 400

        filename = file.filename.lower()

        # Detectar tipo
        if filename.endswith(".pdf"):
            file_type = "PDF"
        elif filename.endswith(".png"):
            file_type = "PNG"
        else:
            file_type = "JPG"

        # OCR API
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": (file.filename, file.stream)},
            data={
                "apikey": "helloworld",
                "language": "eng",
                "filetype": file_type
            }
        )

        result = response.json()
        print("OCR RESPONSE:", result)

        if result.get("IsErroredOnProcessing"):
            return jsonify({"error": str(result.get("ErrorMessage"))}), 500

        text = result["ParsedResults"][0]["ParsedText"].lower()

        print("==== TEXTO OCR ====")
        print(text)
        print("===================")

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
    app.run(host="0.0.0.0", port=5000)
