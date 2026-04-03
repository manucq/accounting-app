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

    # LIMPIEZA
    text = text.lower()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # -----------------------
    # TOTAL (MEJORADO)
    # -----------------------
    total_patterns = [
        r"total\s*\$?\s*(\d+[.,]\d{2})",
        r"amount\s*due\s*\$?\s*(\d+[.,]\d{2})",
        r"balance\s*\$?\s*(\d+[.,]\d{2})"
    ]

    for pattern in total_patterns:
        match = re.search(pattern, text)
        if match:
            data["total"] = float(match.group(1).replace(",", "."))
            break

    # fallback → mayor número
    if data["total"] == 0:
        amounts = re.findall(r"\d+[.,]\d{2}", text)
        if amounts:
            data["total"] = max([float(x.replace(",", ".")) for x in amounts])

    # -----------------------
    # INVOICE
    # -----------------------
    inv = re.search(r"(invoice|inv|bill)[\s#:]*([a-z0-9-]+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    # -----------------------
    # CLIENT (MUCHO MEJOR)
    # -----------------------
    for line in lines[:8]:
        if (
            3 < len(line) < 40
            and not any(x in line for x in ["total","tax","date","invoice","amount","receipt"])
            and not re.search(r"\d", line)
        ):
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
# PROCESS FILE (ESTABLE)
# ---------------------------

@app.route("/process-file", methods=["POST"])
def process_file():
    try:
        file = request.files.get("file")

        if not file:
            return jsonify({"error": "No file"}), 400

        filename = file.filename.lower()

        # 🔥 detectar tipo archivo
        if filename.endswith(".pdf"):
            file_type = "PDF"
        elif filename.endswith(".png"):
            file_type = "PNG"
        else:
            file_type = "JPG"

        # 🔥 limitar tamaño (evita crash)
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)

        if size > 2 * 1024 * 1024:
            return jsonify({"error": "File too large (max 2MB)"}), 400

        # 🔥 OCR con timeout
        try:
            response = requests.post(
                "https://api.ocr.space/parse/image",
                 files={"file": (file.filename, file.stream, file.content_type)},
                 data={
                     "apikey": API_KEY,
                     "language": "eng",
                     "isOverlayRequired": False
                 },
                 timeout=10
        )
        except:
            return jsonify({"error": "OCR timeout, try smaller image"}), 500

        result = response.json()

        print("OCR RESPONSE:", result)

        if result.get("IsErroredOnProcessing"):
            return jsonify({"error": str(result.get("ErrorMessage"))}), 500

        text = parsed["ParsedResults"][0].get("ParsedText", "").lower()

        print("==== TEXTO OCR ====")
        print(text)
        print("===================")

        data = extract_data(text)

        # si no detecta monto
        if data["total"] == 0:
            return jsonify(dict(zip(
                ["income","expenses","profit","annual"],
                totals()
            )))

        # guardar
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
