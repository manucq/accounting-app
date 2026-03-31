from flask import Flask, request, jsonify, send_file, redirect, session
from flask_cors import CORS
import pandas as pd
import sqlite3
import socket

app = Flask(__name__)
app.secret_key = "secret123"

# =====================================================
# CREAR BASE DE DATOS
# =====================================================

def create_tables():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # usuarios
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # archivos subidos
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
        <style>
            body { background:#f4f6f8; font-family:Arial; display:flex; justify-content:center; align-items:center; height:100vh; }
            .box { background:white; padding:30px; border-radius:12px; width:300px; text-align:center; box-shadow:0 4px 15px rgba(0,0,0,0.1); }
            input { width:100%; padding:10px; margin-top:10px; }
            button { width:100%; padding:12px; margin-top:15px; background:#2ecc71; border:none; color:white; font-size:16px; border-radius:8px; }
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

    user = session["user"]

    return f"""
    <html>
    <head>
        <title>Dashboard</title>

        <style>
            body {{ font-family:Arial; background:#f4f6f8; margin:0; }}
            .header {{ background:#2c3e50; color:white; padding:20px; font-size:22px; }}
            .container {{ padding:20px; max-width:1100px; margin:auto; }}

            .box {{
                background:white;
                padding:20px;
                border-radius:12px;
                margin-bottom:20px;
                box-shadow:0 4px 10px rgba(0,0,0,0.08);
            }}

            input {{ padding:10px; margin-top:10px; width:100%; max-width:300px; }}

            button {{
                padding:12px 20px;
                background:#2ecc71;
                color:white;
                border:none;
                border-radius:8px;
                margin-top:10px;
            }}

        </style>
    </head>

    <body>

        <div class="header">
            💼 Accounting Dashboard | User: {user}
            <br>
            <a href="/logout" style="color:white;">Cerrar sesión</a>
        </div>

        <div class="container">

            <div class="box">
                <h3>Upload Excel</h3>
                <input type="file" id="fileInput">
                <br>
                <button onclick="upload()">Upload File</button>
            </div>

            <div class="box">
                <h3>Create User</h3>

                <form method="POST" action="/create-user">
                    <input type="text" name="user" placeholder="Username"><br>
                    <input type="password" name="password" placeholder="Password"><br>
                    <button type="submit">Create User</button>
                </form>
            </div>

            <div class="box">
                <h3>My Uploaded Files</h3>
                <div id="files"></div>
            </div>

        </div>

        <script>

        function upload() {{

            let file = document.getElementById("fileInput").files[0];

            let formData = new FormData();
            formData.append("file", file);

            fetch("/process", {{
                method:"POST",
                body:formData
            }})
            .then(res=>res.json())
            .then(data=>{{
                alert("File processed successfully");
                loadFiles();
            }});
        }}

        function loadFiles(){{
            fetch("/my-files")
            .then(res=>res.text())
            .then(data=>{{ document.getElementById("files").innerHTML = data; }});
        }}

        loadFiles();

        </script>

    </body>
    </html>
    """


# =====================================================
# CREAR USUARIO DESDE DASHBOARD
# =====================================================

@app.route("/create-user", methods=["POST"])
def create_user():

    if "logged" not in session:
        return redirect("/login")

    user = request.form["user"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, password))
        conn.commit()
    except:
        return "User already exists"

    conn.close()

    return redirect("/dashboard")


# =====================================================
# PROCESAR EXCEL Y GUARDAR POR USUARIO
# =====================================================

@app.route("/process", methods=["POST"])
def process_files():

    if "logged" not in session:
        return jsonify({"error":"not logged"})

    user = session["user"]

    file = request.files["file"]
    df = pd.read_excel(file)

    month = pd.Timestamp.now().strftime("%B")
    year = pd.Timestamp.now().strftime("%Y")

    filename = f"{user}_{month}_{year}.xlsx"

    df.to_excel(filename, index=False)

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO uploads (username, filename, month, year)
        VALUES (?, ?, ?, ?)
    """, (user, filename, month, year))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


# =====================================================
# VER SOLO ARCHIVOS DEL USUARIO
# =====================================================

@app.route("/my-files")
def my_files():

    if "logged" not in session:
        return redirect("/login")

    user = session["user"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT filename, month, year FROM uploads WHERE username=?", (user,))
    files = c.fetchall()

    conn.close()

    html = ""

    for f in files:
        html += f"<p>{f[0]} - {f[1]} {f[2]}</p>"

    return html


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
