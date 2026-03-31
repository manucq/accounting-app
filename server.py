from flask import Flask, request, jsonify, send_file
import os
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime

# ----------------------------------------------------
# CONFIGURACIÓN RENDER + OCR
# ----------------------------------------------------

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
EXCEL_FILE = "accounting_data.xlsx"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ruta correcta de tesseract en Render
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# ----------------------------------------------------
# CREAR EXCEL AUTOMÁTICO
# ----------------------------------------------------

if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=[
        "Date",
        "Type",
        "Store / Client",
        "Category",
        "Amount"
    ])
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# OCR MEJORADO PARA RECIBOS
# ----------------------------------------------------

def read_receipt_text(image_path):

    img = cv2.imread(image_path)

    if img is None:
        return ""

    # aumentar resolución (muy importante para recibos)
    img = cv2.resize(img, None, fx=1.5, fy=1.5)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # eliminar ruido
    gray = cv2.GaussianBlur(gray, (5,5), 0)

    # mejorar contraste
    gray = cv2.adaptiveThreshold(
        gray,255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,2
    )

    text = pytesseract.image_to_string(gray)
    return text.lower()

# ----------------------------------------------------
# EXTRAER MONTO (TOTAL)
# ----------------------------------------------------

def extract_amount(text):

    matches = re.findall(r"\d+\.\d{2}", text)

    if not matches:
        return 0

    # el monto más alto casi siempre es el total
    return max([float(m) for m in matches])

# ----------------------------------------------------
# DETECTAR TIENDA AUTOMÁTICO
# ----------------------------------------------------

def detect_store(text):

    stores = [
        "home depot",
        "lowes",
        "shell",
        "exxon",
        "bp",
        "walmart",
        "costco",
        "amazon",
        "harbor freight"
    ]

    for store in stores:
        if store in text:
            return store.title()

    # primera línea del recibo suele ser la tienda
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) > 3:
            return line.title()

    return "Unknown Store"

# ----------------------------------------------------
# DETECTAR INGRESO (DEPÓSITO)
# ----------------------------------------------------

def detect_income(text):

    keywords = [
        "deposit",
        "direct deposit",
        "payment received",
        "credited",
        "zelle",
        "bank deposit"
    ]

    for k in keywords:
        if k in text:
            return True

    return False

# ----------------------------------------------------
# CLASIFICAR GASTO AUTOMÁTICO
# ----------------------------------------------------

def classify_expense(text):

    if "gas" in text or "fuel" in text:
        return "Fuel"

    if any(word in text for word in ["drill","hammer","saw","tool","blade","cutter"]):
        return "Tools"

    if any(word in text for word in ["wood","cement","paint","tile","pvc","pipe","brick"]):
        return "Materials"

    return "Other Expense"

# ----------------------------------------------------
# GUARDAR EN EXCEL
# ----------------------------------------------------

def save_record(record_type, name, category, amount):

    df = pd.read_excel(EXCEL_FILE)

    new_row = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Type": record_type,
        "Store / Client": name,
        "Category": category,
        "Amount": amount
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# CALCULAR RESULTADOS AUTOMÁTICOS
# ----------------------------------------------------

def calculate_totals():

    df = pd.read_excel(EXCEL_FILE)

    income = df[df["Type"]=="Income"]["Amount"].sum()
    expenses = df[df["Type"]=="Expense"]["Amount"].sum()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ----------------------------------------------------
# SUBIR FOTO Y PROCESAR AUTOMÁTICO
# ----------------------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "file" not in request.files:
        return jsonify({"error":"No file uploaded"})

    file = request.files["file"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    # leer texto del recibo
    text = read_receipt_text(path)

    amount = extract_amount(text)

    if amount == 0:
        income, expenses, profit, annual = calculate_totals()
        return jsonify({
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "annual": annual
        })

    # detectar ingreso
    if detect_income(text):
        save_record("Income","Client Payment","Income",amount)

    else:
        store = detect_store(text)
        category = classify_expense(text)
        save_record("Expense",store,category,amount)

    income, expenses, profit, annual = calculate_totals()

    return jsonify({
        "income": income,
        "expenses": expenses,
        "profit": profit,
        "annual": annual
    })

# ----------------------------------------------------
# DESCARGAR EXCEL
# ----------------------------------------------------

@app.route("/download")
def download():
    return send_file(EXCEL_FILE, as_attachment=True)

# ----------------------------------------------------
# RENDER SERVER
# ----------------------------------------------------

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
