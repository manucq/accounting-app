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
# TESSERACT (WINDOWS + RENDER)
# ----------------------------------------------------

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

# ----------------------------------------------------
# CREATE EXCEL FILE IF NOT EXISTS
# ----------------------------------------------------

if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=[
        "Date",
        "Type",
        "Client / Store",
        "Invoice Number",
        "Category",
        "Amount"
    ])
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# SERVE HTML
# ----------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# ----------------------------------------------------
# IMAGE PREPROCESSING (OPTIMIZADO PARA CELULAR)
# ----------------------------------------------------

def preprocess_image(path):

    img = cv2.imread(path)

    if img is None:
        print("ERROR: imagen no cargó")
        return None

    # reducir tamaño (esto evita que Render se quede sin memoria)
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

def read_receipt(path):

    processed = preprocess_image(path)

    if processed is None:
        return ""

    text = pytesseract.image_to_string(processed)
    return text.lower()

# ----------------------------------------------------
# EXTRACT AMOUNT
# ----------------------------------------------------

def extract_amount(text):

    matches = re.findall(r"\d+\.\d{2}", text)

    if not matches:
        return 0

    return max([float(x) for x in matches])

# ----------------------------------------------------
# EXTRACT INVOICE DATA (NUEVO)
# ----------------------------------------------------

def extract_invoice_data(text):

    data = {
        "date": "",
        "client": "",
        "invoice": "",
        "amount": 0
    }

    # DATE
    date_patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{4}-\d{2}-\d{2}"
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data["date"] = match.group()
            break

    # INVOICE NUMBER
    invoice_patterns = [
        r"invoice\s*#?\s*(\w+)",
        r"invoice\s*no\.?\s*(\w+)",
        r"inv\s*#?\s*(\w+)"
    ]

    for pattern in invoice_patterns:
        match = re.search(pattern, text)
        if match:
            data["invoice"] = match.group(1)
            break

    # AMOUNT
    amounts = re.findall(r"\d+\.\d{2}", text)
    if amounts:
        data["amount"] = max([float(x) for x in amounts])

    # CLIENT NAME (primeras líneas del texto)
    lines = text.split("\n")

    for line in lines[:10]:
        line = line.strip()

        if len(line) > 4 and len(line) < 40:
            if not any(x in line for x in ["invoice", "date", "total", "amount", "tax"]):
                data["client"] = line.title()
                break

    return data

# ----------------------------------------------------
# DETECT STORE
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
        "amazon"
    ]

    for store in stores:
        if store in text:
            return store.title()

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) > 3:
            return line.title()

    return "Unknown Store"

# ----------------------------------------------------
# DETECT INCOME
# ----------------------------------------------------

def detect_income(text):

    keywords = [
        "deposit",
        "payment received",
        "direct deposit",
        "zelle",
        "credited"
    ]

    for k in keywords:
        if k in text:
            return True

    return False

# ----------------------------------------------------
# CLASSIFY EXPENSE
# ----------------------------------------------------

def classify_expense(text):

    if "gas" in text or "fuel" in text:
        return "Fuel"

    if any(w in text for w in ["drill","hammer","saw","tool","blade","cutter"]):
        return "Tools"

    if any(w in text for w in ["wood","cement","paint","tile","pvc","pipe","brick"]):
        return "Materials"

    return "Other Expense"

# ----------------------------------------------------
# SAVE DATA
# ----------------------------------------------------

def save_record(record_type, name, category, amount, invoice=""):

    df = pd.read_excel(EXCEL_FILE)

    new_row = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Type": record_type,
        "Client / Store": name,
        "Invoice Number": invoice,
        "Category": category,
        "Amount": amount
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# CALCULATE TOTALS
# ----------------------------------------------------

def calculate_totals():

    df = pd.read_excel(EXCEL_FILE)

    income = df[df["Type"] == "Income"]["Amount"].sum()
    expenses = df[df["Type"] == "Expense"]["Amount"].sum()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ----------------------------------------------------
# PROCESS FILE (FUNCIONA EN CELULAR + RENDER)
# ----------------------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"})

    # nombre fijo compatible con iPhone
    filename = "upload.jpg"
    path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(path)

    text = read_receipt(path)

    invoice_data = extract_invoice_data(text)

    amount = invoice_data["amount"]
    client = invoice_data["client"]
    invoice_number = invoice_data["invoice"]

    if amount == 0:
        income, expenses, profit, annual = calculate_totals()
        return jsonify({
            "income": float(income),
            "expenses": float(expenses),
            "profit": float(profit),
            "annual": float(annual)
        })

    if detect_income(text):
        save_record("Income", client or "Client Payment", "Income", amount, invoice_number)
    else:
        store = detect_store(text)
        category = classify_expense(text)
        save_record("Expense", store, category, amount, invoice_number)

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
# RUN SERVER
# ----------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
