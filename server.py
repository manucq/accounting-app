from flask import Flask, request, jsonify, send_file, send_from_directory
import os
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime
import platform

# ----------------------------------------------------
# APP CONFIG
# ----------------------------------------------------

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
EXCEL_FILE = "accounting_data.xlsx"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------------------------------
# TESSERACT CONFIG (WINDOWS + RENDER)
# ----------------------------------------------------

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

# ----------------------------------------------------
# CREATE EXCEL FILE (IF NOT EXISTS)
# ----------------------------------------------------

if not os.path.exists(EXCEL_FILE):

    df = pd.DataFrame(columns=[
        "Date",
        "Month",
        "Type",
        "Client / Store",
        "Invoice Number",
        "Category",
        "Subtotal",
        "Tax",
        "Amount"
    ])

    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# HOME PAGE
# ----------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ----------------------------------------------------
# IMAGE PREPROCESSING (OPTIMIZED FOR MOBILE)
# ----------------------------------------------------

def preprocess_image(path):

    img = cv2.imread(path)

    if img is None:
        return None

    # Reduce size to avoid memory crash (Render fix)
    img = cv2.resize(img, (1000, 1200))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    gray = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    return gray

# ----------------------------------------------------
# OCR
# ----------------------------------------------------

def read_text_from_image(path):

    processed = preprocess_image(path)

    if processed is None:
        return ""

    text = pytesseract.image_to_string(processed)
    return text.lower()

# ----------------------------------------------------
# SMART EXTRACTION (PRO LEVEL)
# ----------------------------------------------------

def extract_accounting_data(text):

    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "client": "",
        "invoice": "",
        "subtotal": 0,
        "tax": 0,
        "total": 0
    }

    # DATE
    date_patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}-\d{2}-\d{4}"
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data["date"] = match.group()
            break

    # INVOICE NUMBER
    inv = re.search(r"(invoice|inv|bill)\s*#?\s*(\w+)", text)
    if inv:
        data["invoice"] = inv.group(2)

    # SUBTOTAL
    sub = re.search(r"subtotal\s*\$?\s*(\d+\.\d{2})", text)
    if sub:
        data["subtotal"] = float(sub.group(1))

    # TAX
    tax = re.search(r"(tax|vat)\s*\$?\s*(\d+\.\d{2})", text)
    if tax:
        data["tax"] = float(tax.group(2))

    # TOTAL
    total = re.search(r"(total|amount due)\s*\$?\s*(\d+\.\d{2})", text)
    if total:
        data["total"] = float(total.group(2))
    else:
        amounts = re.findall(r"\d+\.\d{2}", text)
        if amounts:
            data["total"] = max([float(x) for x in amounts])

    # CLIENT NAME (first valid line)
    lines = text.split("\n")

    for line in lines[:10]:
        line = line.strip()

        if len(line) > 4 and len(line) < 40:
            if not any(x in line.lower() for x in ["invoice","total","date","tax","receipt"]):
                data["client"] = line.title()
                break

    return data

# ----------------------------------------------------
# AUTO EXPENSE CLASSIFICATION
# ----------------------------------------------------

def classify_expense(text):

    if "gas" in text or "fuel" in text:
        return "Fuel"

    if any(w in text for w in ["drill","hammer","tool","saw","blade"]):
        return "Tools"

    if any(w in text for w in ["wood","cement","paint","pipe","pvc","tile","brick"]):
        return "Materials"

    if any(w in text for w in ["restaurant","food","cafe","coffee"]):
        return "Food"

    return "Other Expense"

# ----------------------------------------------------
# SAVE RECORD
# ----------------------------------------------------

def save_record(data, record_type):

    df = pd.read_excel(EXCEL_FILE)

    month = datetime.now().strftime("%Y-%m")

    new_row = pd.DataFrame([{
        "Date": data["date"],
        "Month": month,
        "Type": record_type,
        "Client / Store": data["client"],
        "Invoice Number": data["invoice"],
        "Category": classify_expense(data["client"]),
        "Subtotal": data["subtotal"],
        "Tax": data["tax"],
        "Amount": data["total"]
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# MONTHLY REPORT (AUTOMATIC)
# ----------------------------------------------------

def generate_monthly_report():

    df = pd.read_excel(EXCEL_FILE)

    monthly = df.groupby("Month")["Amount"].sum().reset_index()

    return monthly.to_dict(orient="records")

# ----------------------------------------------------
# TOTALS
# ----------------------------------------------------

def calculate_totals():

    df = pd.read_excel(EXCEL_FILE)

    income = df[df["Type"] == "Income"]["Amount"].sum()
    expenses = df[df["Type"] == "Expense"]["Amount"].sum()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ----------------------------------------------------
# PROCESS FILE
# ----------------------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    try:

        # Verificar que llegó archivo
        if "file" not in request.files:
            return jsonify({"error": "file not received"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "empty filename"}), 400

        # Guardar archivo con nombre simple (esto arregla iPhone)
        filename = "upload.jpg"
        path = os.path.join(UPLOAD_FOLDER, filename)

        file.save(path)

        # Leer texto con OCR
        text = read_text_from_image(path)

        # Extraer datos
        data = extract_accounting_data(text)

        amount = data["total"]

        # Si no detecta monto, no guarda nada pero devuelve totales
        if amount == 0:
            income, expenses, profit, annual = calculate_totals()
            return jsonify({
                "income": float(income),
                "expenses": float(expenses),
                "profit": float(profit),
                "annual": float(annual)
            })

        # Guardar ingreso o gasto
        if "deposit" in text or "payment received" in text:
            save_record(data, "Income")
        else:
            save_record(data, "Expense")

        # Calcular totales actualizados
        income, expenses, profit, annual = calculate_totals()

        return jsonify({
            "income": float(income),
            "expenses": float(expenses),
            "profit": float(profit),
            "annual": float(annual)
        })

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]

    filename = file.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    text = read_text_from_image(path)

    data = extract_accounting_data(text)

    if data["total"] == 0:
        income, expenses, profit, annual = calculate_totals()
        return jsonify({
            "income": float(income),
            "expenses": float(expenses),
            "profit": float(profit),
            "annual": float(annual)
        })

    if "payment received" in text or "deposit" in text:
        save_record(data, "Income")
    else:
        save_record(data, "Expense")

    income, expenses, profit, annual = calculate_totals()

    return jsonify({
        "income": float(income),
        "expenses": float(expenses),
        "profit": float(profit),
        "annual": float(annual)
    })

# ----------------------------------------------------
# DOWNLOAD EXCEL
# ----------------------------------------------------

@app.route("/download")
def download():
    return send_file(EXCEL_FILE, as_attachment=True)

# ----------------------------------------------------
# MONTHLY REPORT ENDPOINT
# ----------------------------------------------------

@app.route("/monthly-report")
def monthly_report():
    return jsonify(generate_monthly_report())

# ----------------------------------------------------
# RUN SERVER
# ----------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
