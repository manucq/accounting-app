from flask import Flask, request, jsonify, send_file, send_from_directory

def calculate_totals():

    df = pd.read_excel(EXCEL_FILE)

    income = df[df["Type"] == "Income"]["Amount"].sum()
    expenses = df[df["Type"] == "Expense"]["Amount"].sum()

    profit = income - expenses
    annual = profit * 12

    return income, expenses, profit, annual

# ----------------------------------------------------
# PROCESS FILE FROM HTML
# ----------------------------------------------------

@app.route("/process-file", methods=["POST"])
def process_file():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No selected file"})

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    text = read_receipt(path)
    amount = extract_amount(text)

    if amount == 0:
        income, expenses, profit, annual = calculate_totals()
        return jsonify({
            "income": float(income),
            "expenses": float(expenses),
            "profit": float(profit),
            "annual": float(annual)
        })

    if detect_income(text):
        save_record("Income", "Client Payment", "Income", amount)
    else:
        store = detect_store(text)
        category = classify_expense(text)
        save_record("Expense", store, category, amount)

    income, expenses, profit, annual = calculate_totals()

    return jsonify({
        "income": float(income),
        "expenses": float(expenses),
        "profit": float(profit),
        "annual": float(annual)
    })

# ----------------------------------------------------
# DOWNLOAD EXCEL
# ----------------------------------------------------

@app.route("/download")
def download():
    return send_file(EXCEL_FILE, as_attachment=True)

# ----------------------------------------------------
# RUN SERVER (LOCAL + RENDER)
# ----------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
