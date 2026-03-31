from flask import Flask, request, jsonify, redirect, session
import pandas as pd
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret123"


# =====================================================
# CREAR BASE DE DATOS
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            filename TEXT,
            month TEXT,
            year TEXT
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
        <title>Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{background:#f4f6f8;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
            .box{background:white;padding:30px;border-radius:12px;width:300px;text-align:center;box-shadow:0 4px 15px rgba(0,0,0,0.1)}
            input{width:100%;padding:10px;margin-top:10px}
            button{width:100%;padding:12px;margin-top:15px;background:#2ecc71;border:none;color:white;font-size:16px;border-radius:8px}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Accounting Login</h2>
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

            table{{width:100%;margin-top:20px;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}}
            th{{background:#2c3e50;color:white;padding:12px}}
            td{{padding:10px;border-bottom:1px solid #eee}}
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

    <table id="table">
        <thead>
            <tr>
                <th>Description</th>
                <th>Amount</th>
                <th>Type</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>

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
