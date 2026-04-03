from flask import Flask, request, jsonify, render_template, redirect, session
import sqlite3
import os
import re
from datetime import datetime
import requests
from PIL import Image
import io

app = Flask(__name__, template_folder="templates")
app.secret_key = "supersecretkey"

DB = "accounting.db"

# -------------------------
# DATABASE INIT
# -------------------------

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        type TEXT,
        client TEXT,
        total REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# OCR
# -------------------------

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

def ocr_space(file):
    file = compress_image(file)

    try:
        r = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": ("file.jpg", file)},
            data={"apikey": "helloworld"},
            timeout=15
        )
        res = r.json()

        if res.get("IsErroredOnProcessing"):
            return ""

        return res["ParsedResults"][0]["ParsedText"].lower()

    except:
        return ""

# -------------------------
# EXTRACT
# -------------------------

def extract_total(text):
    amounts = re.findall(r"\d+[.,]\d{2}", text)
    if amounts:
        return max([float(x.replace(",", ".")) for x in amounts])
    return 0

# -------------------------
# AUTH
# -------------------------

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
        u = c.fetchone()

        if u:
            session["user_id"] = u[0]
            return redirect("/dashboard")
        else:
            return "Login failed"

    return render_template("login.html")

@app.route("/register", methods=["POST"])
def register():
    user = request.form["username"]
    pw = request.form["password"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("INSERT INTO users (username,password) VALUES (?,?)", (user,pw))
    conn.commit()
    conn.close()

    return redirect("/")

# -------------------------
# DASHBOARD
# -------------------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    return render_template("dashboard.html")

# -------------------------
# PROCESS FILE
# -------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "user_id" not in session:
        return jsonify({"error": "not logged"}), 403

    file = request.files.get("file")

    text = ocr_space(file)

    total = extract_total(text)

    if total == 0:
        return jsonify(get_totals(session["user_id"]))

    tipo = "Income" if "deposit" in text else "Expense"

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO records (user_id,date,type,client,total)
    VALUES (?,?,?,?,?)
    """, (
        session["user_id"],
        datetime.now().strftime("%Y-%m-%d"),
        tipo,
        "Auto",
        total
    ))

    conn.commit()
    conn.close()

    return jsonify(get_totals(session["user_id"]))

# -------------------------
# TOTALS
# -------------------------

def get_totals(user_id):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT SUM(total) FROM records WHERE user_id=? AND type='Income'", (user_id,))
    income = c.fetchone()[0] or 0

    c.execute("SELECT SUM(total) FROM records WHERE user_id=? AND type='Expense'", (user_id,))
    expenses = c.fetchone()[0] or 0

    conn.close()

    profit = income - expenses

    return {
        "income": income,
        "expenses": expenses,
        "profit": profit,
        "annual": profit * 12
    }

# -------------------------
# RUN
# -------------------------

if __name__ == "__main__":
    app.run()
