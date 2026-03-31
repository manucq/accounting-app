from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

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
@app.route("/dashboard")
def dashboard():
    return """
    <html>
    <head>
        <title>Accounting Dashboard</title>

        <style>
            body {
                font-family: Arial;
                background: #f4f6f8;
                margin: 0;
                padding: 20px;
            }

            h1 {
                color: #2c3e50;
            }

            .container {
                max-width: 900px;
                margin: auto;
            }

            .cards {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }

            .card {
                flex: 1;
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }

            .income { color: green; font-size: 28px; font-weight: bold; }
            .expense { color: red; font-size: 28px; font-weight: bold; }

            button {
                background: #2ecc71;
                color: white;
                border: none;
                padding: 12px 18px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                margin-top: 10px;
            }

            button:hover {
                background: #27ae60;
            }

            canvas {
                margin-top: 20px;
            }
        </style>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>

    <body>

    <div class="container">

        <h1>💼 Accounting Dashboard</h1>

        <div class="cards">
            <div class="card">
                <h3>Total Income</h3>
                <div class="income" id="income">$0</div>
            </div>

            <div class="card">
                <h3>Total Expenses</h3>
                <div class="expense" id="expenses">$0</div>
            </div>
        </div>

        <div class="card">
            <h3>Upload Excel File</h3>
            <input type="file" id="fileInput">
            <br>
            <button onclick="upload()">Upload and Calculate</button>
        </div>

        <div class="card">
            <h3>Income vs Expenses</h3>
            <canvas id="chart"></canvas>
        </div>

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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
