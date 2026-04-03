from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
import re
from datetime import datetime
import requests
from PIL import Image
import io

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
DB_FILE = "accounting.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

OCR_API_KEY = "helloworld"

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
# COMPRESS IMAGE
# ---------------------------

def compress_image(file):
    try:
        img = Image.open(file)
        img = img.convert("RGB")
        img.thumbnail((1200, 1200))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)

        return buffer
    except:
        file.seek(0)
        return file

# ---------------------------
# OCR FUNCTION
# ---------------------------

def ocr_space(file):

    file = compress_image(file)

    try:
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": ("file.jpg", file)},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng",
                "OCREngine": 2
            },
            timeout=15
        )

        result = response.json()

        if result.get("IsErroredOnProcessing"):
            return ""

        parsed = result.get("ParsedResults")

        if parsed:
            return parsed[0].get("ParsedText", "").lower()

        return ""

    except:
        return ""

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

    amounts = re.findall(r"\d+[.,]\d{2}", text)

    if amounts:
        values = [float(x.replace(",", ".")) for x in amounts]
        data["total"] = max(values)

    inv = re.search(r"(invoice|inv|bill)\s*#?\s*(\w+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    for line in text.split("\n"):
        line = line.strip()
        if 5 < len(line) < 40 and not any(w in line for w in ["total","invoice","tax","date"]):
            data["client"] = line.title()
            break

    return data

# ---------------------------
# SAVE DATA
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

    file = request.files.get("file")

    if not file:
        return jsonify({"error": "no file"}), 400

    text = ocr_space(file)

    if not text:
        income, expenses, profit, annual = totals()

        return jsonify({
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "annual": annual,
            "warning": "No se pudo leer archivo"
        })

    data = extract_data(text)

    if data["total"] == 0:
        income, expenses, profit, annual = totals()

        return jsonify({
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "annual": annual,
            "warning": "Monto no detectado"
        })

    if "deposit" in text or "payment" in text:
        save(data, "Income")
    else:
        save(data, "Expense")

    income, expenses, profit, annual = totals()

    return jsonify({
        "income": income,
        "expenses": expenses,
        "profit": profit,
        "annual": annual
    })

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
    app.run(host="0.0.0.0", port=10000)
