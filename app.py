from flask import Flask, render_template_string, request, redirect, url_for, send_file
import sqlite3
from datetime import datetime
import csv
from reportlab.platypus import SimpleDocTemplate, Table
from flask import Response
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
# GOOGLE SHEETS SETUP
scope = []
client = None
sheet = None
stock_sheet = None
history_sheet = None
maintenance_sheet = None

try:
    stock_sheet = sheet.worksheet("LIVE_CURRENT_STOCK")
except:
    stock_sheet = sheet.add_worksheet(title="LIVE_CURRENT_STOCK", rows="1000", cols="10")

try:
    history_sheet = sheet.worksheet("STOCK_HISTORY")
except:
    history_sheet = sheet.add_worksheet(title="STOCK_HISTORY", rows="5000", cols="10")

try:
    maintenance_sheet = sheet.worksheet("BUS_MAINTENANCE")
except:
    maintenance_sheet = sheet.add_worksheet(title="BUS_MAINTENANCE", rows="5000", cols="10")


def sync_stock_to_google():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT part_id, name, category, quantity, price, rack
    FROM spare_parts
    ORDER BY name
    """)

    rows = c.fetchall()
    conn.close()

    stock_sheet.clear()

    stock_sheet.append_row([
        "Part ID",
        "Part Name",
        "Category",
        "Current Qty",
        "Price",
        "Rack"
    ])

    for row in rows:
        stock_sheet.append_row(list(row))


def sync_transactions_to_google():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT created_at, txn_type, part_name, quantity, bus_number, mechanic_name, reason
    FROM stock_transactions
    ORDER BY created_at DESC
    """)

    rows = c.fetchall()
    conn.close()

    history_sheet.clear()

    history_sheet.append_row([
        "Date",
        "Type",
        "Part Name",
        "Qty",
        "Bus Number",
        "Employee",
        "Reason"
    ])

    for row in rows:
        history_sheet.append_row(list(row))


def sync_maintenance_to_google():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT created_at, bus_number, mechanic_name, issue_description, parts_used, status
    FROM maintenance_records
    ORDER BY created_at DESC
    """)

    rows = c.fetchall()
    conn.close()

    maintenance_sheet.clear()

    maintenance_sheet.append_row([
        "Date",
        "Bus Number",
        "Employee",
        "Repair Reason",
        "Parts Used",
        "Condition"
    ])

    for row in rows:
        maintenance_sheet.append_row(list(row))
DB = "fleetstock.db"

def get_db():
    return sqlite3.connect(DB)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS spare_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id TEXT UNIQUE,
        name TEXT,
        category TEXT,
        quantity INTEGER,
        price REAL,
        supplier TEXT,
        alert_qty INTEGER,
        rack TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        txn_id TEXT UNIQUE,
        part_id TEXT,
        part_name TEXT,
        txn_type TEXT,
        quantity INTEGER,
        bus_number TEXT,
        mechanic_name TEXT,
        reason TEXT,
        created_at TEXT
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS maintenance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maintenance_id TEXT UNIQUE,
        bus_number TEXT,
        driver_name TEXT,
        issue_description TEXT,
        mechanic_name TEXT,
        parts_used TEXT,
        repair_cost REAL,
        status TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id TEXT UNIQUE,
        name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        parts_supplied TEXT,
        payment_status TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE,
        name TEXT,
        role TEXT,
        phone TEXT,
        shift TEXT,
        experience TEXT
    )
    """)

    conn.commit()
    conn.close()

def next_part_id():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM spare_parts")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"PART{count:03d}"

def next_txn_id():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stock_transactions")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"TXN{count:03d}"

def next_maintenance_id():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM maintenance_records")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"MAIN{count:03d}"

def next_supplier_id():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM suppliers")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"SUP{count:03d}"

def next_employee_id():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM employees")
    count = c.fetchone()[0] + 1
    conn.close()
    return f"EMP{count:03d}"

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ramesh FleetStock Pro</title>

<style>
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: Arial, sans-serif;
}

body {
    background: #f3f7f4;
}

.sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 260px;
    height: 100vh;
    background: #14532d;
    color: white;
    padding: 20px;
}

.brand {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 30px;
}

.nav {
    padding: 14px;
    background: #16a34a;
    margin-bottom: 12px;
    border-radius: 10px;
    cursor: pointer;
}

.nav:hover {
    background: #22c55e;
}

.main {
    margin-left: 260px;
    padding: 25px;
}

.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.topbar h1 {
    color: #14532d;
}

.btn {
    background: #16a34a;
    color: white;
    border: none;
    padding: 12px 18px;
    border-radius: 10px;
    cursor: pointer;
    font-size: 15px;
}

.btn:hover {
    background: #15803d;
}

.cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin-top: 25px;
}

.card {
    background: white;
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
}

.card h3 {
    color: #64748b;
    font-size: 15px;
}

.card p {
    font-size: 28px;
    margin-top: 10px;
    color: #14532d;
    font-weight: bold;
}

.search-box {
    margin-top: 25px;
}

.search-box input {
    width: 100%;
    padding: 14px;
    border-radius: 10px;
    border: 1px solid #ccc;
    font-size: 15px;
}

.table-container {
    margin-top: 25px;
    background: white;
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    background: #dcfce7;
    padding: 12px;
    text-align: left;
}

td {
    padding: 12px;
    border-bottom: 1px solid #eee;
}

.status-badge {
    padding: 6px 12px;
    border-radius: 20px;
    color: white;
    font-weight: bold;
    display: inline-block;
    font-size: 13px;
}

.pending {
    background: #f59e0b;
}

.inprogress {
    background: #2563eb;
}

.completed {
    background: #16a34a;
}

.low-stock {
    color: red;
    font-weight: bold;
}

.delete-btn {
    background: #dc2626;
    color: white;
    padding: 8px 12px;
    text-decoration: none;
    border-radius: 8px;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
}

.modal-content {
    background: white;
    width: 65%;
    margin: 4% auto;
    padding: 25px;
    border-radius: 16px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
}

.form-grid input,
.form-grid textarea,
.form-grid select {
    width: 100%;
    padding: 12px;
    border: 1px solid #ccc;
    border-radius: 10px;
}

.form-grid textarea {
    grid-column: span 2;
}

@media (max-width: 900px) {
    .cards {
        grid-template-columns: repeat(2, 1fr);
    }

    .form-grid {
        grid-template-columns: 1fr;
    }

    .form-grid textarea {
        grid-column: span 1;
    }

    .modal-content {
        width: 90%;
    }
}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>

<body>

<div class="sidebar">
    <div class="brand">Ramesh FleetStock Pro</div>

    <div class="nav" onclick="window.location.href='/'">
        Dashboard
    </div>

    <div class="nav" onclick="window.location.href='/inventory'">
        Inventory
    </div>

    <div class="nav" onclick="window.location.href='/issue_parts'">
        Issue Parts
    </div>

    <div class="nav" onclick="window.location.href='/transactions'">
        Stock Transactions
    </div>

    <div class="nav" onclick="window.location.href='/maintenance'">
        Bus Repairs
    </div>

    <div class="nav" onclick="window.location.href='/employees'">
        Employees
    </div>
    
    <div class="nav" onclick="window.location.href='/vehicle_status'">
        Vehicle Status
    </div>
</div>

<div class="main">
    <div class="topbar">
        <h1>Inventory Dashboard</h1>
        <div>
    <button class="btn" onclick="openModal()">+ Add New Part</button>
</div>
    </div>

    <div class="cards">
    <div class="card">
        <h3>Total Parts</h3>
        <p>{{ total_parts }}</p>
    </div>

    <div class="card">
        <h3>Low Stock</h3>
        <p>{{ low_stock }}</p>
    </div>

    <div class="card">
        <h3>Inventory Value</h3>
        <p>₹{{ total_value }}</p>
    </div>

    <div class="card">
        <h3>Total Transactions</h3>
        <p>{{ total_transactions }}</p>
    </div>

    <div class="card">
        <h3>Total Employees</h3>
        <p>{{ total_employees }}</p>
    </div>

    <div class="card">
        <h3>Pending Repairs</h3>
        <p>{{ pending_repairs }}</p>
    </div>

    <div class="card">
        <h3>Maintenance Cost</h3>
        <p>₹{{ maintenance_cost }}</p>
    </div>
</div>

    <form method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search by name / category / supplier" value="{{ query }}">
    </form>

    <div class="table-container">
        <table>
            <tr>
                <th>Part ID</th>
                <th>Name</th>
                <th>Category</th>
                <th>Quantity</th>
                <th>Price</th>
                <th>Supplier</th>
                <th>Rack</th>
                <th>Action</th>
            </tr>

            {% for part in parts %}
            <tr>
                <td>{{ part[1] }}</td>
                <td>{{ part[2] }}</td>
                <td>{{ part[3] }}</td>
                <td class="{% if part[4] <= part[7] %}low-stock{% endif %}">{{ part[4] }}</td>
                <td>₹{{ part[5] }}</td>
                <td>{{ part[6] }}</td>
                <td>{{ part[8] }}</td>
                <td>
                    <button class="btn" onclick="openStockIn({{ part[0] }})">Stock In</button>
                    <a href="/issue_parts" class="btn">Issue Parts</a>
                    <a href="/edit_part/{{ part[0] }}" class="btn">Edit</a>
                    <a href="/delete/{{ part[0] }}" class="delete-btn"
onclick="return confirm('Are you sure you want to delete this part?')">
Delete
</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</div>

<div id="partModal" class="modal">
    <div class="modal-content">
        <h2>Add New Spare Part</h2>
        <br>

        <form method="POST" action="/add">
            <div class="form-grid">
                <input type="text" name="name" placeholder="Part Name" required>
                <input type="text" name="category" placeholder="Category" required>
                <input type="number" name="quantity" placeholder="Quantity" required>
                <input type="number" step="0.01" name="price" placeholder="Unit Price" required>
                <input type="text" name="supplier" placeholder="Supplier" required>
                <input type="number" name="alert_qty" placeholder="Minimum Alert Quantity" required>
                <input type="text" name="rack" placeholder="Rack Location" required>
                <textarea name="notes" placeholder="Notes"></textarea>
            </div>

            <br>
            <button type="submit" class="btn">Save Part</button>
            <button type="button" class="btn" onclick="closeModal()">Close</button>
        </form>
    </div>
</div>

<div id="stockInModal" class="modal">
    <div class="modal-content">
        <h2>Stock In</h2>
        <br>
        <form id="stockInForm" method="POST">
            <div class="form-grid">
                <input type="number" name="quantity" placeholder="Quantity to Add" required>
                <textarea name="reason" placeholder="Reason (e.g. supplier delivery)" required></textarea>
            </div>

            <br>
            <button type="submit" class="btn">Save</button>
            <button type="button" class="btn" onclick="closeStockIn()">Close</button>
        </form>
    </div>
</div>

<script>
function openModal() {
    document.getElementById("partModal").style.display = "block";
}

function closeModal() {
    document.getElementById("partModal").style.display = "none";
}

function openStockIn(id) {
    document.getElementById("stockInModal").style.display = "block";
    document.getElementById("stockInForm").action = "/stock_in/" + id;
}

function closeStockIn() {
    document.getElementById("stockInModal").style.display = "none";
}

const pie = document.getElementById('pieChart');

if (pie) {
    new Chart(pie, {
        type: 'pie',
        data: {
            labels: {{ categories|tojson }},
            datasets: [{
                data: {{ category_counts|tojson }}
            }]
        },
        options: {
            responsive: true
        }
    });
}
</script>

</body>
</html>
"""

@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        INSERT INTO suppliers
        (supplier_id, name, phone, email, address, parts_supplied, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            next_supplier_id(),
            request.form["name"],
            request.form["phone"],
            request.form["email"],
            request.form["address"],
            request.form["parts_supplied"],
            request.form["payment_status"]
        ))
        conn.commit()

    c.execute("""
    SELECT supplier_id, name, phone, email, address, parts_supplied, payment_status
    FROM suppliers
    ORDER BY id DESC
    """)

    suppliers = c.fetchall()
    conn.close()

    SUPPLIER_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Suppliers</title>
    <style>
    body { font-family: Arial; background: #f3f7f4; padding: 30px; margin: 0; }
    h1 { color: #14532d; }

    .btn {
        background: #16a34a;
        color: white;
        padding: 12px 16px;
        border: none;
        border-radius: 10px;
        text-decoration: none;
        cursor: pointer;
    }

    form {
        background: white;
        padding: 20px;
        border-radius: 14px;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    input, select {
        padding: 12px;
        border: 1px solid #ccc;
        border-radius: 10px;
    }

    table {
        width: 100%;
        background: white;
        border-collapse: collapse;
        margin-top: 25px;
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
    </head>

    <body>
        <h1>Supplier Management</h1>
        <a href="/" class="btn">Back</a>

        <form method="POST">
            <div class="grid">
                <input name="name" placeholder="Supplier Name" required>
                <input name="phone" placeholder="Phone Number" required>
                <input name="email" placeholder="Email" required>
                <input name="address" placeholder="Address" required>
                <input name="parts_supplied" placeholder="Parts Supplied" required>

                <select name="payment_status" required>
                    <option value="">Payment Status</option>
                    <option>Paid</option>
                    <option>Pending</option>
                </select>
            </div>

            <br>
            <button type="submit" class="btn">Save Supplier</button>
        </form>

        <table>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Phone</th>
                <th>Email</th>
                <th>Address</th>
                <th>Parts</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>

            {% for s in suppliers %}
            <tr>
                <td>{{ s[0] }}</td>
                <td>{{ s[1] }}</td>
                <td>{{ s[2] }}</td>
                <td>{{ s[3] }}</td>
                <td>{{ s[4] }}</td>
                <td>{{ s[5] }}</td>
                <td>{{ s[6] }}</td>

                <td>
                    <a href="/edit_supplier/{{ s[0] }}" class="btn">Edit</a>
                    <a href="/delete_supplier/{{ s[0] }}" class="btn" style="background:red;"
onclick="return confirm('Delete this supplier?')">
Delete
</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(SUPPLIER_HTML, suppliers=suppliers)

@app.route("/delete_supplier/<supplier_id>")
def delete_supplier(supplier_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM suppliers WHERE supplier_id=?", (supplier_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("suppliers"))


@app.route("/edit_supplier/<supplier_id>", methods=["GET", "POST"])
def edit_supplier(supplier_id):
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        UPDATE suppliers
        SET name=?, phone=?, email=?, address=?, parts_supplied=?, payment_status=?
        WHERE supplier_id=?
        """, (
            request.form["name"],
            request.form["phone"],
            request.form["email"],
            request.form["address"],
            request.form["parts_supplied"],
            request.form["payment_status"],
            supplier_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("suppliers"))

    c.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,))
    supplier = c.fetchone()
    conn.close()

    EDIT_HTML = """
    <html><body style='font-family:Arial;padding:30px;background:#f3f7f4'>
    <h1>Edit Supplier</h1>
    <form method="POST">
        <input name="name" value="{{ supplier[2] }}"><br><br>
        <input name="phone" value="{{ supplier[3] }}"><br><br>
        <input name="email" value="{{ supplier[4] }}"><br><br>
        <input name="address" value="{{ supplier[5] }}"><br><br>
        <input name="parts_supplied" value="{{ supplier[6] }}"><br><br>

        <select name="payment_status">
            <option>{{ supplier[7] }}</option>
            <option>Paid</option>
            <option>Pending</option>
        </select><br><br>

        <button type="submit">Update Supplier</button>
    </form>
    </body></html>
    """

    return render_template_string(EDIT_HTML, supplier=supplier)

@app.route("/employees", methods=["GET", "POST"])
def employees():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        INSERT INTO employees
        (employee_id, name, role, phone, shift, experience)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            next_employee_id(),
            request.form["name"],
            request.form["role"],
            request.form["phone"],
            request.form["shift"],
            request.form["experience"]
        ))
        conn.commit()

    c.execute("""
    SELECT employee_id, name, role, phone, shift, experience
    FROM employees
    ORDER BY id DESC
    """)

    employees = c.fetchall()
    conn.close()

    EMPLOYEE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Employees</title>
    <style>
    body { font-family: Arial; background: #f3f7f4; padding: 30px; margin: 0; }
    h1 { color: #14532d; }

    .btn {
        background: #16a34a;
        color: white;
        padding: 12px 16px;
        border: none;
        border-radius: 10px;
        text-decoration: none;
        cursor: pointer;
    }

    form {
        background: white;
        padding: 20px;
        border-radius: 14px;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    input {
        padding: 12px;
        border: 1px solid #ccc;
        border-radius: 10px;
    }

    table {
        width: 100%;
        background: white;
        border-collapse: collapse;
        margin-top: 25px;
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
    </head>

    <body>
        <h1>Employee Management</h1>
        <a href="/" class="btn">Back</a>

        <form method="POST">
            <div class="grid">
                <input name="name" placeholder="Employee Name" required>
                <input name="role" placeholder="Role" required>
                <input name="phone" placeholder="Phone" required>
                <input name="shift" placeholder="Shift" required>
                <input name="experience" placeholder="Experience" required>
            </div>
            <br>
            <button type="submit" class="btn">Save Employee</button>
        </form>

        <table>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Role</th>
                <th>Phone</th>
                <th>Shift</th>
                <th>Experience</th>
                <th>Actions</th>
            </tr>

            {% for e in employees %}
            <tr>
                <td>{{ e[0] }}</td>
                <td>{{ e[1] }}</td>
                <td>{{ e[2] }}</td>
                <td>{{ e[3] }}</td>
                <td>{{ e[4] }}</td>
                <td>{{ e[5] }}</td>

                <td>
                    <a href="/edit_employee/{{ e[0] }}" class="btn">Edit</a>
                    <a href="/delete_employee/{{ e[0] }}" class="btn" style="background:red;"
onclick="return confirm('Delete this employee?')">
Delete
</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(EMPLOYEE_HTML, employees=employees)

@app.route("/delete_employee/<employee_id>")
def delete_employee(employee_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM employees WHERE employee_id=?", (employee_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("employees"))


@app.route("/edit_employee/<employee_id>", methods=["GET", "POST"])
def edit_employee(employee_id):
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        UPDATE employees
        SET name=?, role=?, phone=?, shift=?, experience=?
        WHERE employee_id=?
        """, (
            request.form["name"],
            request.form["role"],
            request.form["phone"],
            request.form["shift"],
            request.form["experience"],
            employee_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("employees"))

    c.execute("SELECT * FROM employees WHERE employee_id=?", (employee_id,))
    employee = c.fetchone()
    conn.close()

    EDIT_HTML = """
    <html><body style='font-family:Arial;padding:30px;background:#f3f7f4'>
    <h1>Edit Employee</h1>

    <form method="POST">
        <input name="name" value="{{ employee[2] }}"><br><br>
        <input name="role" value="{{ employee[3] }}"><br><br>
        <input name="phone" value="{{ employee[4] }}"><br><br>
        <input name="shift" value="{{ employee[5] }}"><br><br>
        <input name="experience" value="{{ employee[6] }}"><br><br>

        <button type="submit">Update Employee</button>
    </form>
    </body></html>
    """

    return render_template_string(EDIT_HTML, employee=employee)

@app.route("/maintenance", methods=["GET", "POST"])
def maintenance():
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        INSERT INTO maintenance_records
        (maintenance_id, bus_number, driver_name, issue_description,
         mechanic_name, parts_used, repair_cost, status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_maintenance_id(),
            request.form["bus_number"],
            request.form["driver_name"],
            request.form["issue_description"],
            request.form["mechanic_name"],
            request.form["parts_used"],
            max(0, float(request.form["repair_cost"])),
            request.form["status"],
            request.form["notes"],
            datetime.now().isoformat()
        ))

        conn.commit()
        sync_maintenance_to_google()

    c.execute("""
    SELECT maintenance_id, bus_number, driver_name,
           issue_description, mechanic_name,
           parts_used, repair_cost, status, created_at
    FROM maintenance_records
    ORDER BY id DESC
    """)

    records = c.fetchall()
    conn.close()

    MAINTENANCE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Maintenance Records</title>
    <style>
    body {
        font-family: Arial, sans-serif;
        background: #f3f7f4;
        margin: 0;
        padding: 30px;
    }

    h1 {
        color: #14532d;
    }

    .btn {
        background: #16a34a;
        color: white;
        border: none;
        padding: 12px 16px;
        border-radius: 10px;
        cursor: pointer;
        text-decoration: none;
    }

    form {
        background: white;
        padding: 20px;
        border-radius: 14px;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    input, textarea, select {
        padding: 12px;
        border: 1px solid #ccc;
        border-radius: 10px;
        width: 100%;
    }

    textarea {
        grid-column: span 2;
    }

    table {
        width: 100%;
        background: white;
        border-collapse: collapse;
        margin-top: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
    </head>

    <body>
        <h1>Bus Maintenance Management</h1>
        <a href="/" class="btn">Back to Dashboard</a>

        <form method="POST">
            <div class="grid">
                <input name="bus_number" placeholder="Bus Number" required>
                <input name="driver_name" placeholder="Driver Name" required>
                <input name="issue_description" placeholder="Issue Description" required>
                <input name="mechanic_name" placeholder="Mechanic Name" required>
                <input name="parts_used" placeholder="Parts Used" required>
                <input name="repair_cost" type="number" step="0.01" placeholder="Repair Cost" required>

                <select name="status" required>
                    <option value="">Select Status</option>
                    <option>Pending</option>
                    <option>In Progress</option>
                    <option>Completed</option>
                </select>

                <textarea name="notes" placeholder="Notes"></textarea>
            </div>

            <br>
            <button type="submit" class="btn">Save Maintenance Record</button>
        </form>

        <table>
            <tr>
                <th>ID</th>
                <th>Bus</th>
                <th>Driver</th>
                <th>Issue</th>
                <th>Mechanic</th>
                <th>Parts Used</th>
                <th>Cost</th>
                <th>Status</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
            </tr>

            {% for r in records %}
            <tr>
                <td>{{ r[0] }}</td>
                <td>{{ r[1] }}</td>
                <td>{{ r[2] }}</td>
                <td>{{ r[3] }}</td>
                <td>{{ r[4] }}</td>
                <td>{{ r[5] }}</td>
                <td>₹{{ r[6] }}</td>
                <td>
                {% if r[7] == "Pending" %}
                    <span class="status-badge pending">Pending</span>

                {% elif r[7] == "In Progress" %}
                    <span class="status-badge inprogress">In Progress</span>

                {% else %}
                    <span class="status-badge completed">Completed</span>
                {% endif %}
                </td>
                <td>{{ r[8] }}</td>
                <td>
                    <a href="/edit_maintenance/{{ r[0] }}" class="btn">Edit</a>
                    <a href="/delete_maintenance/{{ r[0] }}" class="btn" style="background:red;"
                    onclick="return confirm('Delete this maintenance record?')">
                    Delete
                    </a>
                </td>

                <td>
                    <a href="/edit_maintenance/{{ r[0] }}" class="btn">Edit</a>
                    <a href="/delete_maintenance/{{ r[0] }}" class="btn" style="background:red;"
                    onclick="return confirm('Delete this maintenance record?')">
                    Delete
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(MAINTENANCE_HTML, records=records)

@app.route("/delete_maintenance/<maintenance_id>")
def delete_maintenance(maintenance_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM maintenance_records WHERE maintenance_id=?", (maintenance_id,))
    conn.commit()
    sync_maintenance_to_google()
    conn.close()
    return redirect(url_for("maintenance"))


@app.route("/edit_maintenance/<maintenance_id>", methods=["GET", "POST"])
def edit_maintenance(maintenance_id):
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        UPDATE maintenance_records
        SET bus_number=?, driver_name=?, issue_description=?,
            mechanic_name=?, parts_used=?, repair_cost=?,
            status=?, notes=?
        WHERE maintenance_id=?
        """, (
            request.form["bus_number"],
            request.form["driver_name"],
            request.form["issue_description"],
            request.form["mechanic_name"],
            request.form["parts_used"],
            max(0, float(request.form["repair_cost"])),
            request.form["status"],
            request.form["notes"],
            maintenance_id
        ))
        conn.commit()
        sync_maintenance_to_google()
        conn.close()
        return redirect(url_for("maintenance"))

    c.execute("SELECT * FROM maintenance_records WHERE maintenance_id=?", (maintenance_id,))
    record = c.fetchone()
    conn.close()

    EDIT_HTML = """
    <html><body style='font-family:Arial;padding:30px;background:#f3f7f4'>
    <h1>Edit Maintenance</h1>

    <form method="POST">
        <input name="bus_number" value="{{ record[2] }}"><br><br>
        <input name="driver_name" value="{{ record[3] }}"><br><br>
        <input name="issue_description" value="{{ record[4] }}"><br><br>
        <input name="mechanic_name" value="{{ record[5] }}"><br><br>
        <input name="parts_used" value="{{ record[6] }}"><br><br>
        <input name="repair_cost" value="{{ record[7] }}"><br><br>

        <select name="status">
            <option>{{ record[8] }}</option>
            <option>Pending</option>
            <option>In Progress</option>
            <option>Completed</option>
        </select><br><br>

        <textarea name="notes">{{ record[9] }}</textarea><br><br>

        <button type="submit">Update Maintenance</button>
    </form>
    </body></html>
    """

    return render_template_string(EDIT_HTML, record=record)

@app.route("/transactions")
def transactions():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT txn_id, part_name, txn_type, quantity,
           bus_number, mechanic_name, reason, created_at
    FROM stock_transactions
    ORDER BY id DESC
    """)

    transactions = c.fetchall()
    conn.close()

    TRANSACTION_HTML = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Transactions</title>

    <style>
    body {
        font-family: Arial, sans-serif;
        background: #f3f7f4;
        margin: 0;
        padding: 30px;
    }

    h1 {
        color: #14532d;
    }

    .btn {
        background: #16a34a;
        color: white;
        padding: 10px 15px;
        text-decoration: none;
        border-radius: 10px;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
    </head>

    <body>
        <h1>Stock Transactions</h1>
        <a href="/" class="btn">Back to Dashboard</a>

        <table>
            <tr>
                <th>TXN ID</th>
                <th>Part Name</th>
                <th>Type</th>
                <th>Quantity</th>
                <th>Bus Number</th>
                <th>Mechanic</th>
                <th>Reason</th>
                <th>Date</th>
            </tr>

            {% for txn in transactions %}
            <tr>
                <td>{{ txn[0] }}</td>
                <td>{{ txn[1] }}</td>
                <td>{{ txn[2] }}</td>
                <td>{{ txn[3] }}</td>
                <td>{{ txn[4] }}</td>
                <td>{{ txn[5] }}</td>
                <td>{{ txn[6] }}</td>
                <td>{{ txn[7] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(TRANSACTION_HTML, transactions=transactions)

@app.route("/")
def home():
    query = request.args.get("q", "")
    conn = get_db()
    c = conn.cursor()

    if query:
        c.execute(
            "SELECT * FROM spare_parts WHERE name LIKE ? OR category LIKE ? OR supplier LIKE ? ORDER BY id DESC",
            (f"%{query}%", f"%{query}%", f"%{query}%")
        )
    else:
        c.execute("SELECT * FROM spare_parts ORDER BY id DESC")

    parts = c.fetchall()

    c.execute("SELECT COUNT(*) FROM spare_parts")
    total_parts = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM spare_parts WHERE quantity <= alert_qty")
    low_stock = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(quantity * price), 0) FROM spare_parts")
    total_value = round(c.fetchone()[0], 2)

    c.execute("SELECT COUNT(*) FROM stock_transactions")
    total_transactions = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM employees")
    total_employees = c.fetchone()[0]
    
    c.execute("SELECT employee_id, name FROM employees")
    employee_list = c.fetchall()

    c.execute("SELECT COUNT(*) FROM maintenance_records WHERE status='Pending'")
    pending_repairs = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(repair_cost), 0) FROM maintenance_records")
    maintenance_cost = round(c.fetchone()[0], 2)

    c.execute("""
    SELECT category, COUNT(*)
    FROM spare_parts
    GROUP BY category
    """)
    category_data = c.fetchall()

    categories = [x[0] for x in category_data]
    category_counts = [x[1] for x in category_data]

    conn.close()

    return render_template_string(
    HTML,
    parts=parts,
    total_parts=total_parts,
    low_stock=low_stock,
    total_value=total_value,
    total_transactions=total_transactions,
    total_employees=total_employees,
    employee_list=employee_list,
    pending_repairs=pending_repairs,
    maintenance_cost=maintenance_cost,
    categories=categories,
    category_counts=category_counts,
    query=query
)

@app.route("/inventory")
def inventory():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT *
    FROM spare_parts
    ORDER BY name
    """)

    parts = c.fetchall()
    conn.close()

    INVENTORY_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Inventory</title>
    <style>
    body {
        font-family: Arial;
        background: #f3f7f4;
        padding: 30px;
        margin: 0;
    }

    h1 {
        color: #14532d;
    }

    .btn {
        background: #16a34a;
        color: white;
        padding: 10px 14px;
        border-radius: 10px;
        text-decoration: none;
    }

    table {
        width: 100%;
        background: white;
        border-collapse: collapse;
        margin-top: 20px;
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
    </head>

    <body>
        <h1>Full Inventory Stock</h1>
        <a href="/" class="btn">Back</a>

        <table>
            <tr>
                <th>Part ID</th>
                <th>Name</th>
                <th>Category</th>
                <th>Stock</th>
                <th>Price</th>
                <th>Supplier</th>
                <th>Rack</th>
            </tr>

            {% for p in parts %}
            <tr>
                <td>{{ p[1] }}</td>
                <td>{{ p[2] }}</td>
                <td>{{ p[3] }}</td>
                <td>{{ p[4] }}</td>
                <td>₹{{ p[5] }}</td>
                <td>{{ p[6] }}</td>
                <td>{{ p[8] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(INVENTORY_HTML, parts=parts)

@app.route("/add", methods=["POST"])
def add_part():
    conn = get_db()
    c = conn.cursor()

    part_id = next_part_id()

    name = " ".join(request.form["name"].strip().title().split())
    category = " ".join(request.form["category"].strip().title().split())

    quantity = int(request.form["quantity"])
    price = float(request.form["price"])

    supplier = request.form["supplier"]

    alert_qty = int(request.form["alert_qty"])

    rack = request.form["rack"].strip().upper()

    notes = request.form["notes"].strip()

    c.execute(
        "SELECT id, quantity FROM spare_parts WHERE LOWER(name)=LOWER(?)",
        (name,)
    )

    existing_part = c.fetchone()

    if existing_part:
        new_qty = existing_part[1] + quantity

        c.execute(
            "UPDATE spare_parts SET quantity=? WHERE id=?",
            (new_qty, existing_part[0])
        )

    else:
        c.execute("""
        INSERT INTO spare_parts
        (part_id, name, category, quantity, price, supplier, alert_qty, rack, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            part_id,
            name,
            category,
            quantity,
            price,
            supplier,
            alert_qty,
            rack,
            notes,
            datetime.now().isoformat()
        ))

    conn.commit()

    sync_stock_to_google()
    sync_transactions_to_google()

    conn.close()

    return redirect(url_for("home"))

@app.route("/stock_in/<int:item_id>", methods=["POST"])
def stock_in(item_id):
    conn = get_db()
    c = conn.cursor()

    quantity = int(request.form["quantity"])

    if quantity <= 0:
        conn.close()
        return redirect(url_for("home"))
    reason = request.form["reason"]

    c.execute("SELECT part_id, name, quantity FROM spare_parts WHERE id=?", (item_id,))
    part = c.fetchone()

    if part:
        new_qty = part[2] + quantity

        c.execute(
            "UPDATE spare_parts SET quantity=? WHERE id=?",
            (new_qty, item_id)
        )

        c.execute("""
        INSERT INTO stock_transactions
        (txn_id, part_id, part_name, txn_type, quantity, bus_number, mechanic_name, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_txn_id(),
            part[0],
            part[1],
            "IN",
            quantity,
            "",
            "",
            reason,
            datetime.now().isoformat()
        ))

        conn.commit()

        sync_stock_to_google()
        sync_transactions_to_google()

        conn.close()
        return redirect(url_for("home"))


@app.route("/stock_out/<int:item_id>", methods=["POST"])
def stock_out(item_id):
    conn = get_db()
    c = conn.cursor()

    quantity = int(request.form["quantity"])

    if quantity <= 0:
        conn.close()
        return redirect(url_for("home"))
    bus_number = request.form["bus_number"]
    mechanic_name = request.form["mechanic_name"]
    reason = request.form["reason"]
    vehicle_condition = request.form["vehicle_condition"]

    c.execute("SELECT part_id, name, quantity FROM spare_parts WHERE id=?", (item_id,))
    part = c.fetchone()

    if part:
        current_qty = part[2]

        if quantity > 0 and quantity <= current_qty:
            new_qty = current_qty - quantity

            c.execute(
                "UPDATE spare_parts SET quantity=? WHERE id=?",
                (new_qty, item_id)
            )

            c.execute("""
        INSERT INTO stock_transactions
        (txn_id, part_id, part_name, txn_type, quantity, bus_number, mechanic_name, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_txn_id(),
            part[0],
            part[1],
            "OUT",
            quantity,
            bus_number,
            mechanic_name,
            reason,
            datetime.now().isoformat()
        ))

        c.execute("""
        INSERT INTO maintenance_records
        (maintenance_id, bus_number, driver_name, issue_description,
        mechanic_name, parts_used, repair_cost, status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"MAIN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            bus_number,
            "",
            reason,
            mechanic_name,
            f"{part[1]} x {quantity}",
            0,
            vehicle_condition,
            "Auto created from part issue",
            datetime.now().isoformat()
        ))

        conn.commit()

        sync_stock_to_google()
        sync_transactions_to_google()
        sync_maintenance_to_google()

        conn.close()
        return redirect(url_for("home"))

@app.route("/edit_part/<int:item_id>", methods=["GET", "POST"])
def edit_part(item_id):
    conn = get_db()
    c = conn.cursor()

    if request.method == "POST":
        c.execute("""
        UPDATE spare_parts
        SET name=?, category=?, quantity=?, price=?, supplier=?, alert_qty=?, rack=?, notes=?
        WHERE id=?
        """, (
            request.form["name"],
            request.form["category"],
            int(request.form["quantity"]),
            float(request.form["price"]),
            request.form["supplier"],
            int(request.form["alert_qty"]),
            request.form["rack"],
            request.form["notes"],
            item_id
        ))
        conn.commit()

        sync_stock_to_google()

        conn.close()
        return redirect(url_for("home"))
    c.execute("SELECT * FROM spare_parts WHERE id=?", (item_id,))
    part = c.fetchone()
    conn.close()

    EDIT_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Edit Part</title>
    <style>
    body {
        font-family: Arial;
        background: #f3f7f4;
        padding: 30px;
    }

    form {
        background: white;
        padding: 20px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    input, textarea {
        padding: 12px;
        border: 1px solid #ccc;
        border-radius: 10px;
    }

    textarea {
        grid-column: span 2;
    }

    .btn {
        background: #16a34a;
        color: white;
        padding: 12px 16px;
        border: none;
        border-radius: 10px;
        text-decoration: none;
        cursor: pointer;
    }
    </style>
    </head>

    <body>
        <h1>Edit Spare Part</h1>

        <form method="POST">
            <div class="grid">
                <input name="name" value="{{ part[2] }}" required>
                <input name="category" value="{{ part[3] }}" required>
                <input name="quantity" type="number" value="{{ part[4] }}" required>
                <input name="price" type="number" step="0.01" value="{{ part[5] }}" required>
                <input name="supplier" value="{{ part[6] }}" required>
                <input name="alert_qty" type="number" value="{{ part[7] }}" required>
                <input name="rack" value="{{ part[8] }}" required>
                <textarea name="notes">{{ part[9] }}</textarea>
            </div>

            <br>
            <button type="submit" class="btn">Update Part</button>
            <a href="/" class="btn">Back</a>
        </form>
    </body>
    </html>
    """

    return render_template_string(EDIT_HTML, part=part)

@app.route("/delete/<int:item_id>")
def delete_part(item_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM spare_parts WHERE id=?", (item_id,))
    conn.commit()

    sync_stock_to_google()

    conn.close()
    return redirect(url_for("home"))

@app.route("/issue_parts", methods=["GET", "POST"])
def issue_parts():
    conn = get_db()
    c = conn.cursor()

    # PASTE HERE ↓↓↓
    if request.method == "POST":
        employee = request.form["employee"]
        bus_number = request.form["bus_number"]
        reason = request.form["reason"]
        vehicle_condition = request.form["vehicle_condition"]

        part_ids = request.form.getlist("part_ids")
        quantities = request.form.getlist("quantities")

        used_parts = []
        selected_parts = set()

        for part_id, qty in zip(part_ids, quantities):
            if not part_id or not qty:
                continue

            if part_id in selected_parts:
                continue

            selected_parts.add(part_id)

            qty = int(qty)

            if qty <= 0:
                continue

            c.execute("SELECT part_id, name, quantity FROM spare_parts WHERE id=?", (part_id,))
            part = c.fetchone()

            if part and qty <= part[2]:
                new_qty = part[2] - qty

                c.execute(
                    "UPDATE spare_parts SET quantity=? WHERE id=?",
                    (new_qty, part_id)
                )

                c.execute("""
                INSERT INTO stock_transactions
                (txn_id, part_id, part_name, txn_type, quantity, bus_number, mechanic_name, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    next_txn_id(),
                    part[0],
                    part[1],
                    "OUT",
                    qty,
                    bus_number,
                    employee,
                    reason,
                    datetime.now().isoformat()
                ))

                used_parts.append(f"{part[1]} x {qty}")

        if not used_parts:
            conn.close()
            return redirect(url_for("issue_parts"))

        c.execute("""
        INSERT INTO maintenance_records
        (maintenance_id, bus_number, driver_name, issue_description,
         mechanic_name, parts_used, repair_cost, status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"MAIN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            bus_number,
            "",
            reason,
            employee,
            ", ".join(used_parts),
            0,
            vehicle_condition,
            "Auto created from issue parts",
            datetime.now().isoformat()
        ))

        conn.commit()

        sync_stock_to_google()
        sync_transactions_to_google()
        sync_maintenance_to_google()

        conn.close()
        return redirect(url_for("home"))

    # existing code continues below
    c.execute("SELECT id, name, quantity FROM spare_parts ORDER BY name")
    parts = c.fetchall()

    c.execute("SELECT employee_id, name FROM employees ORDER BY name")
    employees = c.fetchall()

    conn.close()

    ISSUE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Issue Parts</title>

    <style>
    body {
        font-family: Arial;
        background: #f3f7f4;
        padding: 30px;
        margin: 0;
    }

    h1 {
        color: #14532d;
    }

    .btn {
        background: #16a34a;
        color: white;
        padding: 12px 16px;
        border: none;
        border-radius: 10px;
        cursor: pointer;
        text-decoration: none;
    }

    form {
        background: white;
        padding: 20px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        margin-top: 20px;
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    input, select, textarea {
        padding: 12px;
        border: 1px solid #ccc;
        border-radius: 10px;
        width: 100%;
    }

    textarea {
        grid-column: span 2;
    }
    </style>
    </head>

    <body>
        <h1>Issue Parts to Bus</h1>
        <a href="/" class="btn">Back</a>

        <form method="POST">
            <div class="grid">

                <select name="employee" required>
                    <option value="">Select Employee</option>
                    {% for emp in employees %}
                    <option value="{{ emp[1] }}">{{ emp[1] }}</option>
                    {% endfor %}
                </select>

                <input type="text" name="bus_number" placeholder="Bus Number" required>

                <div id="partsContainer" style="grid-column: span 2;"></div>

                <button type="button" class="btn" onclick="addPartRow()">+ Add Part</button>

                <textarea name="reason" placeholder="Repair Reason" required></textarea>

                <select name="vehicle_condition" required>
                    <option>Good</option>
                    <option>Needs Service</option>
                    <option>Under Repair</option>
                    <option>Critical</option>
                </select>

            </div>

            <br>
            <button class="btn">Submit</button>
        </form>
        <script>
let partIndex = 0;

function addPartRow() {
    const container = document.getElementById("partsContainer");

    const row = document.createElement("div");
    row.style.display = "grid";
    row.style.gridTemplateColumns = "2fr 1fr";
    row.style.gap = "10px";
    row.style.marginBottom = "10px";

    row.innerHTML = `
        <select name="part_ids" required>
            <option value="">Select Part</option>
            {% for part in parts %}
            <option value="{{ part[0] }}">{{ part[1] }} (Stock: {{ part[2] }})</option>
            {% endfor %}
        </select>

        <input type="number" name="quantities" placeholder="Quantity" min="1" required>
    `;

    container.appendChild(row);
}

window.onload = function() {
    addPartRow();
};
</script>
    </body>
    </html>
    """

    return render_template_string(
        ISSUE_HTML,
        parts=parts,
        employees=employees
    )

@app.route("/vehicle_status")
def vehicle_status():
    query = request.args.get("q", "")

    bus_query = request.args.get("bus", "")

    conn = get_db()
    c = conn.cursor()

    if bus_query:
        c.execute("""
        SELECT bus_number,
            status,
            issue_description,
            mechanic_name,
            created_at
        FROM maintenance_records
        WHERE bus_number LIKE ?
        ORDER BY created_at DESC
        """, (f"%{bus_query}%",))
    else:
        c.execute("""
        SELECT m1.bus_number,
            m1.status,
            m1.issue_description,
            m1.mechanic_name,
            m1.created_at
        FROM maintenance_records m1
        WHERE m1.created_at = (
            SELECT MAX(m2.created_at)
            FROM maintenance_records m2
            WHERE m2.bus_number = m1.bus_number
        )
        ORDER BY m1.created_at DESC
        """)

    records = c.fetchall()

    all_records = records

    good_count = len([r for r in all_records if r[1] == "Good"])
    needs_service_count = len([r for r in all_records if r[1] == "Needs Service"])
    under_repair_count = len([r for r in all_records if r[1] == "Under Repair"])
    critical_count = len([r for r in all_records if r[1] == "Critical"])

    total_buses = len(all_records)

    conn.close()

    VEHICLE_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>Vehicle Status Dashboard</title>

    <style>
    body {
        font-family: Arial;
        background: #f3f7f4;
        padding: 30px;
        margin: 0;
    }

    h1 {
        color: #14532d;
    }

    .btn {
        background: #16a34a;
        color: white;
        padding: 12px 16px;
        border-radius: 10px;
        text-decoration: none;
    }

    table {
        width: 100%;
        background: white;
        border-collapse: collapse;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }

    th {
        background: #dcfce7;
        padding: 12px;
    }

    td {
        padding: 12px;
        border-bottom: 1px solid #eee;
    }
    
    .status-badge {
    padding: 6px 12px;
    border-radius: 20px;
    color: white;
    font-weight: bold;
    display: inline-block;
    font-size: 13px;
}

.pending {
    background: #f59e0b;
}

.inprogress {
    background: #2563eb;
}

.completed {
    background: #16a34a;
}
    </style>
    </head>

    <body>
        <h1>Vehicle Status Dashboard</h1>
        <a href="/" class="btn">Back</a>

<br><br>

<div style="display:grid; grid-template-columns:repeat(5,1fr); gap:15px; margin-top:20px;">
    <div style="background:white; padding:20px; border-radius:14px;">
        <h3>Total Buses</h3>
        <h2>{{ total_buses }}</h2>
    </div>

    <div style="background:white; padding:20px; border-radius:14px;">
        <h3>Good</h3>
        <h2>{{ good_count }}</h2>
    </div>

    <div style="background:white; padding:20px; border-radius:14px;">
        <h3>Needs Service</h3>
        <h2>{{ needs_service_count }}</h2>
    </div>

    <div style="background:white; padding:20px; border-radius:14px;">
        <h3>Under Repair</h3>
        <h2>{{ under_repair_count }}</h2>
    </div>

    <div style="background:white; padding:20px; border-radius:14px;">
        <h3>Critical</h3>
        <h2>{{ critical_count }}</h2>
    </div>
</div>

<br>

<form method="GET">
    <input type="text" name="bus" placeholder="Search Bus Number"
           value="{{ bus_query }}"
           style="padding:12px; width:300px; border:1px solid #ccc; border-radius:10px;">
    <button class="btn" type="submit">Search</button>
</form>

        <table>
            <tr>
                <th>Bus Number</th>
                <th>Condition</th>
                <th>Repair Work</th>
                <th>Employee</th>
                <th>Date</th>
            </tr>

            {% for r in records %}
            <tr>
                <td>{{ r[0] }}</td>
                <td>
                {% if r[1] == "Good" %}
                    <span class="status-badge completed">Good</span>

                {% elif r[1] == "Needs Service" %}
                    <span class="status-badge pending">Needs Service</span>

                {% elif r[1] == "Under Repair" %}
                    <span class="status-badge inprogress">Under Repair</span>

                {% else %}
                    <span class="status-badge" style="background:red;">Critical</span>
                {% endif %}
                </td>
                <td>{{ r[2] }}</td>
                <td>{{ r[3] }}</td>
                <td>{{ r[4] }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """

    return render_template_string(
    VEHICLE_HTML,
    records=records,
    bus_query=bus_query,
    total_buses=total_buses,
    good_count=good_count,
    needs_service_count=needs_service_count,
    under_repair_count=under_repair_count,
    critical_count=critical_count
)

@app.route("/inventory_pdf")
def inventory_pdf():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT part_id, name, category, quantity, price, supplier
    FROM spare_parts
    """)
    rows = c.fetchall()
    conn.close()

    pdf_file = "inventory_report.pdf"

    data = [["Part ID", "Name", "Category", "Qty", "Price", "Supplier"]]

    for row in rows:
        data.append(list(row))

    pdf = SimpleDocTemplate(pdf_file)
    table = Table(data)
    pdf.build([table])

    return send_file(pdf_file, as_attachment=True)

@app.route("/export_inventory")
def export_inventory():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM spare_parts")
    rows = c.fetchall()
    conn.close()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "Part ID", "Name", "Category", "Quantity",
            "Price", "Supplier", "Alert Qty", "Rack", "Notes"
        ])

        for row in rows:
            yield data.writerow([
                row[1], row[2], row[3], row[4],
                row[5], row[6], row[7], row[8], row[9]
            ])

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":
                    "attachment; filename=inventory.csv"})


@app.route("/export_suppliers")
def export_suppliers():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM suppliers")
    rows = c.fetchall()
    conn.close()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "Supplier ID", "Name", "Phone", "Email",
            "Address", "Parts", "Payment Status"
        ])

        for row in rows:
            yield data.writerow(row[1:])

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":
                    "attachment; filename=suppliers.csv"})


@app.route("/export_employees")
def export_employees():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM employees")
    rows = c.fetchall()
    conn.close()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "Employee ID", "Name", "Role",
            "Phone", "Shift", "Experience"
        ])

        for row in rows:
            yield data.writerow(row[1:])

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":
                    "attachment; filename=employees.csv"})


@app.route("/export_maintenance")
def export_maintenance():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM maintenance_records")
    rows = c.fetchall()
    conn.close()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "Maintenance ID", "Bus", "Driver", "Issue",
            "Mechanic", "Parts Used", "Cost", "Status"
        ])

        for row in rows:
            yield data.writerow([
                row[1], row[2], row[3], row[4],
                row[5], row[6], row[7], row[8]
            ])

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":
                    "attachment; filename=maintenance.csv"})


@app.route("/export_transactions")
def export_transactions():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM stock_transactions")
    rows = c.fetchall()
    conn.close()

    def generate():
        data = csv.writer(Echo())
        yield data.writerow([
            "TXN ID", "Part", "Type", "Qty",
            "Bus", "Mechanic", "Reason"
        ])

        for row in rows:
            yield data.writerow([
                row[1], row[3], row[4], row[5],
                row[6], row[7], row[8]
            ])

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":
                    "attachment; filename=transactions.csv"})


class Echo:
    def write(self, value):
        return value

@app.route("/backup_db")
def backup_db():
    return send_file(
        DB,
        as_attachment=True,
        download_name="RameshFleetStock_Backup.db"
    )

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)