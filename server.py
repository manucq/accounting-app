from flask import Flask, request, jsonify, redirect, session, send_file
import os
import cv2
import pytesseract
import pandas as pd
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "files"
EXCEL_FILE = "accounting_auto.xlsx"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ======================================================
# CREAR EXCEL AUTOMÁTICO
# ======================================================

if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=["Date","Month","Type","Store/Source","Category","Amount","File"])
    df.to_excel(EXCEL_FILE, index=False)

# ======================================================
# LEER TEXTO DESDE FOTO (recibo o screenshot banco)
# ======================================================

def read_text(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]
    text = pytesseract.image_to_string(gray)
    return text

# ======================================================
# EXTRAER MONTO AUTOMÁTICO
# ======================================================

def extract_amount(text):
    matches = re.findall(r"\d+\.\d{2}", text)
    if matches:
        return max([float(m) for m in matches])
    return 0

# ======================================================
# DETECTAR INGRESO AUTOMÁTICO (screenshots banco)
# ======================================================

def detect_income(text):
    t = text.lower()

    keywords = [
        "deposit",
        "payment received",
        "zelle received",
        "direct deposit",
        "credited",
        "incoming transfer"
    ]

    for k in keywords:
        if k in t:
            return True

    return False

# ======================================================
# DETECTAR TIENDA (si es gasto)
# ======================================================

def detect_store(text):
    t = text.lower()

    if "home depot" in t:
        return "Home Depot"

    if "lowes" in t:
        return "Lowes"

    if "shell" in t or "gas" in t:
        return "Gas Station"

    if "walmart" in t:
        return "Walmart"

    return "Unknown"

# ======================================================
# CLASIFICAR GASTO AUTOMÁTICO
# ======================================================

def classify(store):

    if store in ["Home Depot","Lowes"]:
        return "Materials"

    if store == "Gas Station":
        return "Fuel"

    if store == "Walmart":
        return "Tools"

    return "Other Expense"

# ======================================================
# DETECTAR DUPLICADOS
# ======================================================

def is_duplicate(amount):
    df = pd.read_excel(EXCEL_FILE)
    if amount in df["Amount"].values:
        return True
    return False

# ======================================================
# GUARDAR EN EXCEL AUTOMÁTICO
# ======================================================

def save_record(record_type, source, category, amount, file):

    df = pd.read_excel(EXCEL_FILE)

    new_row = {
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Month": datetime.now().strftime("%B"),
        "Type": record_type,
        "Store/Source": source,
        "Category": category,
        "Amount": amount,
        "File": file
    }

    df = df.append(new_row, ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# ======================================================
# LOGIN
# ======================================================

@app.route("/")
def home():
    return redirect("/login")

@app.route("/login")
def login():
    return "<h2>Login</h2><form method='POST' action='/login-check'><input name='user'><input name='password'><button>Login</button></form>"

@app.route("/login-check", methods=["POST"])
def login_check():

    if request.form["user"] == "admin" and request.form["password"] == "1234":
        session["logged"] = True
        return redirect("/dashboard")

    return "Login incorrect"

# ======================================================
# DASHBOARD CON ESCÁNER AUTOMÁTICO
# ======================================================

@app.route("/dashboard")
def dashboard():

    if "logged" not in session:
        return redirect("/login")

    return """
    <h2>📸 Auto Scanner (Recibos + Depósitos del banco)</h2>

    <video id="video" autoplay playsinline width="350"></video>
    <canvas id="canvas" style="display:none"></canvas>

    <h3 id="status">Buscando recibo o depósito...</h3>

    <script>

    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const status = document.getElementById("status");

    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then(stream => {
        video.srcObject = stream;
        autoScan();
    });

    function autoScan(){

        setInterval(() => {

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            const ctx = canvas.getContext("2d");
            ctx.drawImage(video,0,0);

            canvas.toBlob(blob => {

                const formData = new FormData();
                formData.append("file", blob, "scan.jpg");

                fetch("/process-file",{
                    method:"POST",
                    body:formData
                })
                .then(res=>res.json())
                .then(data=>{
                    if(data.saved){
                        status.innerHTML = "Guardado automáticamente ✅";
                    }
                });

            });

        },3000);
    }

    </script>

    <br><br>
    <a href="/download">📥 Descargar Excel automático</a>
    """

# ======================================================
# PROCESAR IMAGEN (detecta ingreso o gasto)
# ======================================================

@app.route("/process-file", methods=["POST"])
def process_file():

    file = request.files["file"]

    path = os.path.join(UPLOAD_FOLDER,file.filename)
    file.save(path)

    text = read_text(path)
    amount = extract_amount(text)

    if amount == 0:
        return jsonify({"saved":False})

    if is_duplicate(amount):
        return jsonify({"saved":False})

    # ingreso
    if detect_income(text):
        save_record("Income","Bank Deposit","Income",amount,file.filename)
        return jsonify({"saved":True})

    # gasto
    store = detect_store(text)
    category = classify(store)

    save_record("Expense",store,category,amount,file.filename)
    return jsonify({"saved":True})

# ======================================================
# DESCARGAR EXCEL
# ======================================================

@app.route("/download")
def download():
    return send_file(EXCEL_FILE, as_attachment=True)

# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
