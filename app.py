from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date, datetime

app = Flask(__name__)
DB = "netlink.db"

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect(DB)

def init_db():
    con = get_db()
    cur = con.cursor()

    # Users table OPTIONAL (future ke liye, ab use nahi ho rahi)
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

# ---------- DASHBOARD (HOME) ----------
@app.route("/")
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        entry_date = request.form.get("date") or date.today().isoformat()
        person = request.form.get("name")
        amount = float(request.form.get("amount"))
        entry_type = request.form.get("type")

        credit = amount if entry_type == "credit" else 0
        debit = amount if entry_type == "debit" else 0

        cur.execute("SELECT balance FROM ledger ORDER BY id DESC LIMIT 1")
        last = cur.fetchone()
        last_balance = last[0] if last else 0

        balance = last_balance + credit - debit

        cur.execute(
            "INSERT INTO ledger VALUES (NULL,?,?,?,?,?,?)",
            (entry_date, person, credit, debit, "NetLink Team", balance)
        )
        con.commit()

    cur.execute("SELECT SUM(credit), SUM(debit) FROM ledger")
    credit, debit = cur.fetchone()
    credit = credit or 0
    debit = debit or 0
    balance = credit - debit

    con.close()

    return render_template(
        "dashboard.html",
        credit=credit,
        debit=debit,
        balance=balance,
        today=date.today().isoformat()
    )

# ---------- ENTRIES ----------
@app.route("/entries")
def entries():

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM ledger ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()

    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "date": datetime.strptime(r[1], "%Y-%m-%d").strftime("%d %b %Y"),
            "person": r[2],
            "credit": r[3],
            "debit": r[4],
            "balance": r[6]
        })

    return render_template("entries.html", data=data)

# ---------- MONTHLY REPORT ----------
@app.route("/monthly-report", methods=["GET", "POST"])
def monthly_report():

    selected_month = request.form.get("month") or date.today().strftime("%Y-%m")

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT * FROM ledger
        WHERE entry_date LIKE ?
        ORDER BY entry_date DESC
    """, (f"{selected_month}%",))

    rows = cur.fetchall()

    total_credit = 0
    total_debit = 0
    data = []

    for r in rows:
        total_credit += r[3]
        total_debit += r[4]

        data.append({
            "date": datetime.strptime(r[1], "%Y-%m-%d").strftime("%d %b %Y"),
            "person": r[2],
            "credit": r[3],
            "debit": r[4],
            "balance": r[6]
        })

    con.close()

    return render_template(
        "monthly_report.html",
        data=data,
        total_credit=total_credit,
        total_debit=total_debit,
        net_balance=total_credit - total_debit,
        selected_month=selected_month
    )

# ---------- DELETE ----------
@app.route("/delete/<int:id>")
def delete(id):

    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM ledger WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect(url_for("entries"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
