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

# 🔑 PON TU API KEY AQUÍ
API_KEY = "K82953514288957"

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
# COMPRESS IMAGE (FIX 1MB)
# ---------------------------

def compress_image(file):

    try:
        img = Image.open(file.stream)

        # convertir a RGB
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 🔥 REDUCIR TAMAÑO (CLAVE)
        img.thumbnail((800, 800))  # máximo 800px

        buffer = io.BytesIO()

        # 🔥 compresión fuerte
        img.save(buffer, format="JPEG", quality=25, optimize=True)

        buffer.seek(0)

        print("SIZE AFTER COMPRESS (KB):", len(buffer.getvalue()) / 1024)

        return buffer

    except Exception as e:
        print("ERROR COMPRESS:", e)
        return file.stream

# ---------------------------
# OCR FUNCTION
# ---------------------------

def ocr_space(file):

    compressed = compress_image(file)

    try:
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={
                "file": ("image.jpg", compressed, "image/jpeg")
            },
            data={
                "apikey": API_KEY,
                "language": "eng"
            },
            timeout=20
        )

        result = response.json()

        print("OCR RESPONSE:", result)

        if result.get("IsErroredOnProcessing"):
            return ""

        text = result["ParsedResults"][0].get("ParsedText", "").lower()

        print("==== TEXTO OCR ====")
        print(text)
        print("===================")

        return text

    except Exception as e:
        print("OCR ERROR:", e)
        return ""

# ---------------------------
# EXTRACT DATA (MEJORADO)
# ---------------------------

def extract_data(text):

    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client": "Unknown",
        "invoice": "",
        "total": 0
    }

    text = text.lower()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # TOTAL INTELIGENTE
    patterns = [
        r"total\s*\$?\s*(\d+[.,]\d{2})",
        r"amount\s*due\s*\$?\s*(\d+[.,]\d{2})",
        r"balance\s*\$?\s*(\d+[.,]\d{2})"
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            data["total"] = float(m.group(1).replace(",", "."))
            break

    # fallback
    if data["total"] == 0:
        amounts = re.findall(r"\d+[.,]\d{2}", text)
        if amounts:
            data["total"] = max([float(x.replace(",", ".")) for x in amounts])

    # invoice
    inv = re.search(r"(invoice|inv|bill)[\s#:]*([a-z0-9-]+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    # client inteligente
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

    data = extract_data(text)

    if data["total"] == 0:
        return jsonify(dict(zip(
            ["income","expenses","profit","annual"],
            totals()
        )))

    if "deposit" in text or "payment received" in text:
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
