from flask import Flask, request, jsonify, send_file, redirect, session
from flask_cors import CORS
import pandas as pd
import sqlite3
import socket
import io
import qrcode

app = Flask(__name__)
app.secret_key = "secret123"

# =====================================================
# CREAR BASE DE DATOS Y USUARIOS
# =====================================================

def create_users_table():
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

create_users_table()


def create_default_user():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username='admin'")
    user = c.fetchone()

    if not user:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "1234"))

    conn.commit()
    conn.close()

create_default_user()


# =====================================================
# OBTENER IP LOCAL (para celular)
# =====================================================

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# =====================================================
# RUTA PRINCIPAL
# =====================================================

@app.route("/")
def home():
    return redirect("/login")


# =====================================================
# LOGIN
# =====================================================

@app.route("/login")
def login():
    return """
    <html>
    <head>
        <title>Login</title>

        <style>
            body {
                background: #f4f6f8;
                font-family: Arial;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .login-box {
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
                width: 300px;
                text-align: center;
            }

            input {
                width: 100%;
                padding: 10px;
                margin-top: 10px;
                border-radius: 6px;
                border: 1px solid #ccc;
            }

            button {
                width: 100%;
                padding: 12px;
                margin-top: 15px;
                background: #2ecc71;
                border: none;
                color: white;
                font-size: 16px;
                border-radius: 8px;
            }
        </style>
    </head>

    <body>
        <div class="login-box">
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


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =====================================================
# DASHBOARD (PROTEGIDO)
# =====================================================

@app.route("/dashboard")
def dashboard():

    if "logged" not in session:
        return redirect("/login")

    return """
    <html>
    <head>
        <title>Accounting Dashboard</title>

        <style>
            body {
                margin: 0;
                font-family: Arial;
                background: #f4f6f8;
            }

            .header {
                background: #2c3e50;
                color: white;
                padding: 20px;
                font-size: 22px;
            }

            .container {
                padding: 20px;
                max-width: 1100px;
                margin: auto;
            }

            .cards {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }

            .card {
                flex: 1;
                padding: 25px;
                border-radius: 12px;
                color: white;
                font-size: 20px;
                font-weight: bold;
            }

            .income { background: #2ecc71; }
            .expense { background: #e74c3c; }

            .upload {
                background: white;
                margin-top: 20px;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
            }

            button {
                background: #2ecc71;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                margin-top: 10px;
            }

            canvas {
                margin-top: 25px;
                background: white;
                padding: 20px;
                border-radius: 12px;
            }
        </style>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>

    <body>

        <div class="header">
            💼 Accounting Dashboard | User: """ + session["user"] + """
            <br>
            <a href="/logout" style="color:white;">Cerrar sesión</a>
        </div>

        <div class="container">

            <div class="cards">
                <div class="card income">
                    Total Income
                    <div id="income">$0</div>
                </div>

                <div class="card expense">
                    Total Expenses
                    <div id="expenses">$0</div>
                </div>
            </div>

            <div class="upload">
                <h3>Upload Excel File</h3>
                <input type="file" id="fileInput">
                <br>
                <button onclick="upload()">Upload and Process</button>
            </div>

            <canvas id="chart"></canvas>

        </div>

        <script>

        let chart;

        function upload() {

            let file = document.getElementById("fileInput").files[0];

            let formData = new FormData();
            formData.append("file", file);

            fetch("/process", {
                method: "POST",
                body: formData
            })
            .then(res => res.json())
            .then(data => {

                document.getElementById("income").innerText = "$" + data.income;
                document.getElementById("expenses").innerText = "$" + data.expenses;

                if(chart) chart.destroy();

                chart = new Chart(document.getElementById("chart"), {
                    type: "bar",
                    data: {
                        labels: ["Income", "Expenses"],
                        datasets: [{
                            data: [data.income, data.expenses]
                        }]
                    }
                });

            });

        }

        </script>

    </body>
    </html>
    """


# =====================================================
# PROCESAR EXCEL AUTOMÁTICO
# =====================================================

@app.route("/process", methods=["POST"])
def process_files():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

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
