from flask import Flask, request, jsonify, redirect, session, send_from_directory
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"


# =====================================================
# BASE DE DATOS
# =====================================================

def create_tables():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    conn.commit()
    conn.close()

create_tables()


# =====================================================
# CREAR USUARIO ADMIN AUTOMÁTICO
# =====================================================

def create_admin():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "1234"))

    conn.commit()
    conn.close()

create_admin()


# =====================================================
# PWA FILES (icono y manifest)
# =====================================================

@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json")


@app.route("/icon.png")
def icon():
    return send_from_directory(".", "icon.png")


# =====================================================
# LOGIN
# =====================================================

@app.route("/")
def home():
    return redirect("/login")


@app.route("/login")
def login():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Accounting App</title>

        <meta name="viewport" content="width=device-width, initial-scale=1">

        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#2ecc71">

        <style>

        body{
            margin:0;
            font-family:Arial;
            background:linear-gradient(135deg,#2ecc71,#27ae60);
            height:100vh;
            display:flex;
            justify-content:center;
            align-items:center;
        }

        .box{
            background:white;
            padding:40px;
            border-radius:18px;
            width:300px;
            text-align:center;
            box-shadow:0 10px 30px rgba(0,0,0,0.2);
            animation:fade 0.8s ease;
        }

        @keyframes fade{
            from{opacity:0;transform:translateY(40px);}
            to{opacity:1;transform:translateY(0);}
        }

        h2{
            margin-bottom:20px;
        }

        input{
            width:100%;
            padding:12px;
            margin-top:12px;
            border-radius:8px;
            border:1px solid #ccc;
        }

        button{
            width:100%;
            padding:14px;
            margin-top:18px;
            border:none;
            border-radius:10px;
            background:#2ecc71;
            color:white;
            font-size:16px;
            font-weight:bold;
            cursor:pointer;
        }

        </style>
    </head>

    <body>

        <div class="box">
            <h2>💼 Accounting App</h2>

            <form method="POST" action="/login-check">
                <input type="text" name="user" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
                <button type="submit">Entrar</button>
            </form>

        </div>

    </body>
    </html>
    """


@app.route("/login-check", methods=["POST"])
def login_check():

    user = request.form["user"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, password))
    result = c.fetchone()

    conn.close()

    if result:
        session["logged"] = True
        session["user"] = user
        return redirect("/dashboard")

    return "Login incorrect"


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/dashboard")
def dashboard():

    if "logged" not in session:
        return redirect("/login")

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Accounting Dashboard</title>

    <meta name="viewport" content="width=device-width, initial-scale=1">

    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#2ecc71">

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

body{{font-family:Arial;background:#f4f6f8;margin:0;padding:20px}}

.header{{background:#2c3e50;color:white;padding:20px;font-size:22px}}
.logout{{float:right;color:white;text-decoration:none;font-size:14px}}

.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:20px;margin-top:20px}}

.card{{background:white;padding:20px;border-radius:12px;box-shadow:0 4px 10px rgba(0,0,0,0.08)}}
.green{{border-left:6px solid #2ecc71}}
.red{{border-left:6px solid #e74c3c}}
.blue{{border-left:6px solid #3498db}}

.big{{font-size:28px;font-weight:bold;margin-top:10px}}

button{{padding:12px 20px;border:none;border-radius:8px;background:#2ecc71;color:white;font-weight:bold;cursor:pointer;margin-top:10px}}

</style>
</head>

<body>

<div class="header">
    💼 Accounting Dashboard | User: {session["user"]}
    <a class="logout" href="/logout">Cerrar sesión</a>
</div>

<br>

<input type="file" id="fileInput" accept=".xlsx,.xls"><br>
<button onclick="uploadFile()">Upload Excel</button>

<div class="grid">

    <div class="card green">
        <div>Total Income</div>
        <div class="big" id="income">0</div>
    </div>

    <div class="card red">
        <div>Total Expenses</div>
        <div class="big" id="expenses">0</div>
    </div>

    <div class="card blue">
        <div>Profit</div>
        <div class="big" id="profit">0</div>
    </div>

</div>

<canvas id="chart"></canvas>

<script>

let chart;

function uploadFile(){{

    const file = document.getElementById("fileInput").files[0];

    if(!file){{
        alert("Select a file first");
        return;
    }}

    const formData = new FormData();
    formData.append("file", file);

    fetch("/process",{{
        method:"POST",
        body:formData
    }})
    .then(res=>res.json())
    .then(data=>{{

        document.getElementById("income").innerText = data.income;
        document.getElementById("expenses").innerText = data.expenses;
        document.getElementById("profit").innerText = data.income - data.expenses;

        if(chart) chart.destroy();

        chart = new Chart(document.getElementById("chart"), {{
            type:"bar",
            data:{{
                labels:["Income","Expenses","Profit"],
                datasets:[{{data:[data.income,data.expenses,data.income-data.expenses]}}]
            }}
        }});

    }});

}}

</script>

</body>
</html>
"""


# =====================================================
# PROCESAR EXCEL
# =====================================================

@app.route("/process", methods=["POST"])
def process():

    if "logged" not in session:
        return jsonify({"error":"not logged"})

    file = request.files["file"]
    df = pd.read_excel(file)

    income = 0
    expenses = 0

    for _, row in df.iterrows():
        text = str(row).lower()
        amount = float(row["Amount"])

        if "income" in text:
            income += amount
        else:
            expenses += amount

    return jsonify({
        "income": income,
        "expenses": expenses
    })


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
