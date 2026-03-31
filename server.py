from flask import Flask, request, jsonify, send_file
import os
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
EXCEL_FILE = "accounting_data.xlsx"

STORES_FILE = "learned_stores.txt"
TOOLS_FILE = "learned_tools.txt"
MATERIALS_FILE = "learned_materials.txt"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------------------------------
# CREAR ARCHIVOS SI NO EXISTEN
# ----------------------------------------------------

for f in [STORES_FILE, TOOLS_FILE, MATERIALS_FILE]:
    if not os.path.exists(f):
        open(f, "w").close()

# ----------------------------------------------------
# CREAR EXCEL AUTOMÁTICO
# ----------------------------------------------------

if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=[
        "Date",
        "Type",
        "Client/Store",
        "Category",
        "Amount"
    ])
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# OCR (LEE EL TEXTO DE LA FOTO)
# ----------------------------------------------------

def read_text(path):

    img = cv2.imread(path)

    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray,(5,5),0)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(gray)
    return text.lower()

# ----------------------------------------------------
# EXTRAER MONTO
# ----------------------------------------------------

def extract_amount(text):

    matches = re.findall(r"\d+\.\d{2}", text)

    if matches:
        return max([float(m) for m in matches])

    return 0

# ----------------------------------------------------
# CARGAR PALABRAS APRENDIDAS
# ----------------------------------------------------

def load_words(file):
    with open(file,"r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_word(file, word):
    with open(file,"a") as f:
        f.write(word.lower() + "\n")

# ----------------------------------------------------
# DETECTAR TIENDA (APRENDIZAJE AUTOMÁTICO)
# ----------------------------------------------------

def detect_store(text):

    learned = load_words(STORES_FILE)

    for store in learned:
        if store in text:
            return store.title()

    # detectar nueva tienda automáticamente
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if len(line) > 3:
            save_word(STORES_FILE, line)
            return line.title()

    return "Unknown Store"

# ----------------------------------------------------
# DETECTAR MATERIAL
# ----------------------------------------------------

def detect_material(text):

    learned = load_words(MATERIALS_FILE)

    for word in learned:
        if word in text:
            return True

    material_words = ["cement","wood","pvc","pipe","paint","tile","brick"]

    for w in material_words:
        if w in text:
            save_word(MATERIALS_FILE, w)
            return True

    return False

# ----------------------------------------------------
# DETECTAR TOOLS
# ----------------------------------------------------

def detect_tools(text):

    learned = load_words(TOOLS_FILE)

    for word in learned:
        if word in text:
            return True

    tool_words = ["drill","saw","hammer","tool","blade","cutter"]

    for w in tool_words:
        if w in text:
            save_word(TOOLS_FILE, w)
            return True

    return False

# ----------------------------------------------------
# DETECTAR INGRESO
# ----------------------------------------------------

def detect_income(text):

    keywords = ["deposit","payment received","zelle","credited","direct deposit"]

    for k in keywords:
        if k in text:
            return True

    return False

# ----------------------------------------------------
# CLASIFICAR AUTOMÁTICO
# ----------------------------------------------------

def classify(text):

    if detect_material(text):
        return "Materials"

    if detect_tools(text):
        return "Tools"

    if "gas" in text or "fuel" in text:
        return "Fuel"

    return "Other Expense"

# ----------------------------------------------------
# GUARDAR EN EXCEL (CORREGIDO)
# ----------------------------------------------------

def save_record(record_type, name, category, amount):

    df = pd.read_excel(EXCEL_FILE)

    new_row = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Type": record_type,
        "Client/Store": name,
        "Category": category,
        "Amount": amount
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# ----------------------------------------------------
# CALCULAR RESULTADOS
# ----------------------------------------------------

def calculate_totals():

    df = pd.read_excel(EXCEL_FILE)

    income = df[df["Type"]=="Income"]["Amount"].sum()
    expenses = df[df["Type"]=="Expense"]["Amount"].sum()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ----------------------------------------------------
# PROCESAR FOTO
# ----------------------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    text = read_text(path)
    amount = extract_amount(text)

    # si no detecta monto solo devuelve totales
    if amount == 0:
        income, expenses, profit, annual = calculate_totals()
        return jsonify({
            "income": income,
            "expenses": expenses,
            "profit": profit,
            "annual": annual
        })

    # INGRESO
    if detect_income(text):
        save_record("Income","Client Payment","Income",amount)

    # GASTO
    else:
        store = detect_store(text)
        category = classify(text)
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
# RUN
# ----------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
