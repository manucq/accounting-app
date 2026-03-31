from flask import Flask, request, jsonify, send_file, redirect, session
from flask_cors import CORS
import pandas as pd
import sqlite3
def create_users_table():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
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

app = Flask(__name__)
app.secret_key = "secret123"

# -----------------------------------------
# Obtener IP local automáticamente
# -----------------------------------------
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

# -----------------------------------------
# Ruta principal
# -----------------------------------------
@app.route("/")
def home():
    return redirect("/login")


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

            table {
                width: 100%;
                margin-top: 20px;
                border-collapse: collapse;
                background: white;
                border-radius: 12px;
                overflow: hidden;
            }

            th {
                background: #2c3e50;
                color: white;
                padding: 12px;
            }

            td {
                padding: 10px;
                border-bottom: 1px solid #eee;
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
            💼 Accounting Dashboard
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

            <button onclick="download()">Download Excel Report</button>

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

        function download() {
            window.location.href = "/download";
        }

        </script>

    </body>
    </html>
    """
def home():
    return open("index.html", "r", encoding="utf-8").read()

# -----------------------------------------
# Procesar archivo (PDF o imagen)
# -----------------------------------------
@app.route("/process", methods=["POST"])
def process_files():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]
    df = pd.read_excel(file)

    income = 0
    expenses = 0
    fuel = 0
    materials = 0
    tools = 0

    # Detectar cliente automáticamente
    client = "General"

    for _, row in df.iterrows():

        text = str(row).lower()
        amount = float(row["Amount"])

        if "income" in text:
            income += amount
        else:
            expenses += amount

        if "gas" in text or "fuel" in text:
            fuel += amount

        if "home depot" in text or "lowes" in text or "material" in text:
            materials += amount

        if "tool" in text or "drill" in text or "saw" in text:
            tools += amount

        # detectar cliente si aparece nombre
        if "client" in text:
            client = text

    # -----------------------------
    # ARCHIVO POR MES
    # -----------------------------
    month = pd.Timestamp.now().strftime("%B")
    month_file = f"{month}.xlsx"

    # -----------------------------
    # ARCHIVO ANUAL
    # -----------------------------
    year = pd.Timestamp.now().strftime("%Y")
    year_file = f"{year}.xlsx"

    # -----------------------------
    # ARCHIVO POR CLIENTE
    # -----------------------------
    client_file = f"{client}.xlsx"

    summary = pd.DataFrame({
        "Category": ["Income", "Expenses", "Fuel", "Materials", "Tools"],
        "Total": [income, expenses, fuel, materials, tools]
    })

    # Guardar archivo mensual
    with pd.ExcelWriter(month_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        summary.to_excel(writer, index=False, sheet_name="Summary")

    # Guardar archivo anual
    with pd.ExcelWriter(year_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        summary.to_excel(writer, index=False, sheet_name="Summary")

    # Guardar archivo por cliente
    with pd.ExcelWriter(client_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        summary.to_excel(writer, index=False, sheet_name="Summary")

    return jsonify({
        "income": income,
        "expenses": expenses,
        "fuel": fuel,
        "materials": materials,
        "tools": tools,
        "month_file": month_file,
        "year_file": year_file,
        "client_file": client_file
    })
# -----------------------------------------
# Mostrar IP para abrir desde el celular
# -----------------------------------------
@app.route("/get-ip")
def get_ip():
    return jsonify({"ip": get_local_ip()})

# -----------------------------------------
# Generar código QR automático
# -----------------------------------------
@app.route("/qr")
def get_qr():

    ip = get_local_ip()
    link = f"http://{ip}:5000"

    img = qrcode.make(link)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")

# -----------------------------------------
# Ejecutar servidor
# -----------------------------------------
@app.route("/login")
def login():
    return """
    <html>
    <head>
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
            <h2>Login</h2>

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

