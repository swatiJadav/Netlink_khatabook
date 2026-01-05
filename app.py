from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3, io, os
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- REPORTLAB ----------
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Image, Spacer
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------- APP ----------
app = Flask(__name__)
app.secret_key = "netlink_secret_key"
DB = "netlink.db"

# ---------- FONTS (₹ SYMBOL FIX) ----------
pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", "DejaVuSans-Bold.ttf"))

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect(DB)

def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT,
        person TEXT,
        credit REAL,
        debit REAL,
        added_by TEXT,
        balance REAL
    )
    """)

    con.commit()
    con.close()

init_db()

# ---------- REGISTER ----------
@app.route("/", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        try:
            con = get_db()
            cur = con.cursor()
            cur.execute("INSERT INTO users VALUES (NULL,?,?)", (username, password))
            con.commit()
            con.close()
            return redirect(url_for("login"))
        except:
            return "Username already exists"

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        con.close()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return "Invalid login"

    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        entry_date = request.form.get("entry_date") or str(date.today())
        person = request.form["person"]

        amount = float(request.form["amount"])
        entry_type = request.form["type"]

        credit = amount if entry_type == "credit" else 0
        debit = amount if entry_type == "debit" else 0

        cur.execute(
            "SELECT balance FROM ledger ORDER BY id DESC LIMIT 1"
        )
        last = cur.fetchone()
        last_balance = last[0] if last else 0

        balance = last_balance + credit - debit

        cur.execute(
            "INSERT INTO ledger VALUES (NULL,?,?,?,?,?,?)",
            (entry_date, person, credit, debit, session["user"], balance)
        )
        con.commit()

    cur.execute("SELECT * FROM ledger ORDER BY entry_date DESC")
    entries = cur.fetchall()

    cur.execute("SELECT SUM(credit), SUM(debit) FROM ledger")
    total_credit, total_debit = cur.fetchone()

    total_credit = total_credit or 0
    total_debit = total_debit or 0
    net_balance = total_credit - total_debit

    con.close()

    return render_template(
        "dashboard.html",
        entries=entries,
        today=str(date.today()),
        total_credit=total_credit,
        total_debit=total_debit,
        net_balance=net_balance
    )

# ---------- PDF DOWNLOAD ----------
@app.route("/download_pdf")
def download_pdf():
    if "user" not in session:
        return redirect(url_for("login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT entry_date, person, credit, debit, added_by, balance FROM ledger")
    rows = cur.fetchall()
    con.close()

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)

    styles = getSampleStyleSheet()
    styles["Title"].fontName = "DejaVu-Bold"
    styles["Normal"].fontName = "DejaVu"

    elements = []

    # ---------- LOGO ----------)

    elements.append(Paragraph("Netlink Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    table_data = [["Date", "Person", "Credit", "Debit", "Added By", "Balance"]]

    for r in rows:
        table_data.append([
            r[0],
            r[1],
            f"₹ {r[2]:.2f}",
            f"₹ {r[3]:.2f}",
            r[4],
            f"₹ {r[5]:.2f}"
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "DejaVu"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    pdf.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="Netlink_Khatabook_Report.pdf",
        mimetype="application/pdf"
    )

# ---------- DELETE ----------
@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect(url_for("login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM ledger WHERE id=?", (id,))
    con.commit()
    con.close()
    return redirect(url_for("dashboard"))

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
