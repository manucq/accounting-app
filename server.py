from flask import Flask, request, jsonify, redirect, session, send_file
import pandas as pd
import sqlite3
import os
import pytesseract
import cv2
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "receipts"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =====================================================
# BASE DE DATOS (aprende tiendas automáticamente)
# =====================================================

def create_tables():

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)

    # aprende tiendas automáticamente
    c.execute("""
        CREATE TABLE IF NOT EXISTS stores(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT
        )
    """)

    # guarda transacciones
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            description TEXT,
            amount REAL,
            category TEXT,
            verified TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()

create_tables()

# =====================================================
# APRENDER TIENDAS AUTOMÁTICAMENTE
# =====================================================

def learn_store(text):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    text = text.lower()

    if "home depot" in text:
        c.execute("INSERT INTO stores(name, category) VALUES (?,?)", ("Home Depot","Materials"))

    if "lowes" in text:
        c.execute("INSERT INTO stores(name, category) VALUES (?,?)", ("Lowes","Materials"))

    if "shell" in text or "exxon" in text or "bp" in text:
        c.execute("INSERT INTO stores(name, category) VALUES (?,?)", ("Gas Station","Fuel"))

    if "tools" in text:
        c.execute("INSERT INTO stores(name, category) VALUES (?,?)", ("Tools Store","Tools"))

    conn.commit()
    conn.close()

# =====================================================
# CLASIFICAR AUTOMÁTICO
# =====================================================

def classify(text):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT name, category FROM stores")
    stores = c.fetchall()

    for s in stores:
        if s[0].lower() in text.lower():
            return s[1]

    # reglas básicas
    if "deposit" in text.lower():
        return "Income"

    if "transfer" in text.lower():
        return "Partner Transfer"

    return "Other Expense"

# =====================================================
# OCR (leer recibos)
# =====================================================

def read_receipt(path):

    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(gray)

    return text

# =====================================================
# LOGIN
# =====================================================

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login")
def login():
    return """
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
        body{font-family:Arial;background:#2ecc71;height:100vh;display:flex;justify-content:center;align-items:center;margin:0}
        .box{background:white;padding:30px;border-radius:15px;width:300px;text-align:center}
        input{width:100%;padding:12px;margin-top:10px}
        button{width:100%;padding:12px;margin-top:15px;background:#2ecc71;color:white;border:none;border-radius:8px}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Accounting Login</h2>
            <form method="POST" action="/login-check">
                <input name="user" placeholder="Username">
                <input name="password" type="password" placeholder="Password">
                <button>Entrar</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/login-check", methods=["POST"])
def login_check():

    user = request.form["user"]
    password = request.form["password"]

    if user == "admin" and password == "1234":
        session["logged"] = True
        session["user"] = user
        return redirect("/dashboard")

    return "Login incorrect"

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =====================================================
# DASHBOARD PRO
# =====================================================

@app.route("/dashboard")
def dashboard():

    if "logged" not in session:
        return redirect("/login")

    return f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
        body{{font-family:Arial;background:#f4f6f8;margin:0;padding:20px}}
        .header{{background:#2c3e50;color:white;padding:20px}}
        .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-top:20px}}
        .card{{background:white;padding:20px;border-radius:10px}}
        button{{padding:12px 20px;background:#2ecc71;color:white;border:none;border-radius:8px;margin-top:10px}}
        </style>
    </head>
    <body>

    <div class="header">
        Accounting Dashboard | {session["user"]}
        <a href="/logout" style="color:white;float:right">Cerrar sesión</a>
    </div>

    <h3>Subir estado de cuenta</h3>
    <input type="file" id="bank"><br>
    <button onclick="bank()">Procesar</button>

    <h3>Tomar foto del recibo</h3>
    <input type="file" id="receipt" accept="image/*" capture="environment"><br>
    <button onclick="receipt()">Subir recibo</button>

    <script>

    function bank(){{
        let f = document.getElementById("bank").files[0];
        let fd = new FormData();
        fd.append("file",f);

        fetch("/process-bank",{{method:"POST",body:fd}})
        .then(res=>res.json())
        .then(d=>alert("Income: "+d.income+" | Expenses: "+d.expenses));
    }}

    function receipt(){{
        let f = document.getElementById("receipt").files[0];
        let fd = new FormData();
        fd.append("file",f);

        fetch("/process-receipt",{{method:"POST",body:fd}})
        .then(res=>res.json())
        .then(d=>alert("Categoría detectada: "+d.category));
    }}

    </script>

    </body>
    </html>
    """

# =====================================================
# PROCESAR RECIBO (aprende solo)
# =====================================================

@app.route("/process-receipt", methods=["POST"])
def process_receipt():

    file = request.files["file"]
    path = os.path.join(UPLOAD_FOLDER,file.filename)
    file.save(path)

    text = read_receipt(path)

    # aprende automáticamente
    learn_store(text)

    category = classify(text)

    return jsonify({"category":category})

# =====================================================
# PROCESAR ESTADO DE CUENTA
# =====================================================

@app.route("/process-bank", methods=["POST"])
def process_bank():

    file = request.files["file"]
    df = pd.read_excel(file)

    income = 0
    expenses = 0

    for _, row in df.iterrows():

        desc = str(row[1])
        amount = float(row[2])

        category = classify(desc)

        if category == "Income":
            income += amount
        else:
            expenses += amount

    return jsonify({"income":income,"expenses":expenses})

# =====================================================
# GENERAR EXCEL NJ TAXES
# =====================================================

@app.route("/download")
def download():

    data = {
        "Category":["Income","Materials","Tools","Fuel","Insurance","Phone","Other"],
        "Amount":[10000,3000,1500,1200,900,600,400]
    }

    df = pd.DataFrame(data)
    file = "NJ_tax_report.xlsx"
    df.to_excel(file,index=False)

    return send_file(file,as_attachment=True)

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000)
