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
                background: #f5f6fa;
                margin: 0;
                padding: 20px;
            }
            .card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0px 3px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
            }
            .income { color: green; font-size: 24px; }
            .expense { color: red; font-size: 24px; }
        </style>
    </head>

    <body>

    <h1>📊 Accounting Dashboard</h1>

    <div class="card">
        <h3>Total Income</h3>
        <div class="income">$0</div>
    </div>

    <div class="card">
        <h3>Total Expenses</h3>
        <div class="expense">$0</div>
    </div>

    <div class="card">
        <h3>Upload File</h3>
        <input type="file" id="fileInput">
        <button onclick="upload()">Upload</button>
    </div>

    <script>
        function upload() {
            let file = document.getElementById("fileInput").files[0];

            let formData = new FormData();
            formData.append("file", file);

            fetch("/process", {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                document.querySelector(".income").innerText = "$" + data.income;
                document.querySelector(".expense").innerText = "$" + data.expenses;
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
def process_file():

    income = 0
    expenses = 0
    fuel = 0
    materials = 0
    tools = 0

    materials_detected = []

    file = request.files.get("file")

    if not file:
        return jsonify({
            "income":0,
            "expenses":0,
            "fuel":0,
            "materials":0,
            "tools":0,
            "profit":0,
            "top_materials":[]
        })

    # Leer archivo
    text = file.read().decode("latin-1", errors="ignore")
    lines = text.split("\n")

    # Procesar líneas
    for line in lines:

        line_upper = line.upper()

        if "$" in line:

            try:
                amount = float(line.split("$")[-1].replace(",", "").strip())
            except:
                continue

            # INCOME
            if "DEPOSIT" in line_upper:
                income += amount
                continue

            # GASOLINA
            if "SPEEDWAY" in line_upper or "SUNOCO" in line_upper or "EXXON" in line_upper:
                fuel += amount
                expenses += amount
                continue

            # MATERIALES
            if "HOME DEPOT" in line_upper or "LOWES" in line_upper:

                materials += amount
                expenses += amount

                # guardar material detectado
                materials_detected.append(line.strip())

                continue

            # TOOLS
            if "TOOLS" in line_upper:
                tools += amount
                expenses += amount
                continue

            # OTROS GASTOS
            expenses += amount

    profit = income - expenses

    # Detectar materiales más usados automáticamente
    from collections import Counter

    counter = Counter(materials_detected)

    top_materials = []

    for item in counter.most_common(5):
        top_materials.append(item[0])

    # Respuesta final
    return jsonify({
        "income": round(income,2),
        "expenses": round(expenses,2),
        "fuel": round(fuel,2),
        "materials": round(materials,2),
        "tools": round(tools,2),
        "profit": round(profit,2),
        "top_materials": top_materials
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
