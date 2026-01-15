from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = "netlink_secret_key"
DB = "netlink.db"

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
            (entry_date, person, credit, debit, session["user"], balance)
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
    if "user" not in session:
        return redirect(url_for("login"))

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
    if "user" not in session:
        return redirect(url_for("login"))

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
    if "user" not in session:
        return redirect(url_for("login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM ledger WHERE id=?", (id,))
    con.commit()
    con.close()

    return redirect(url_for("entries"))

# ---------- FORGOT PASSWORD ----------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form["username"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        # Password match check
        if new_password != confirm_password:
            return "Passwords do not match"

        # Hash new password
        hashed_password = generate_password_hash(new_password)

        con = get_db()
        cur = con.cursor()

        # Check user exists
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()

        if not user:
            con.close()
            return "User not found"

        # Update password
        cur.execute(
            "UPDATE users SET password=? WHERE username=?",
            (hashed_password, username)
        )
        con.commit()
        con.close()

        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run()
