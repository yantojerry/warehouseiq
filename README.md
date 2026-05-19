    # WarehouseIQ — Store Management System
### A PyQt5 Desktop App solving 6 real-world business bottlenecks

Quick run instructions are in [RUNNING.md](./RUNNING.md).
The desktop app now uses the FastAPI backend as its data layer.

---

##  Project Structure

```
warehouse_system/
├── main.py                   ← Entry point (run this)
├── requirements.txt          ← Python dependencies
│
├── database/
│   └── db_manager.py         ← DB connection, table creation, seed data
│
├── ui/
│   ├── main_window.py        ← Main window + sidebar navigation
│   ├── dashboard.py          ← Overview stats + low stock alerts
│   ├── inventory.py          ← Real-time inventory (Bottleneck 2 & 3)
│   ├── orders.py             ← Order queue / picking list (Bottleneck 1 & 4)
│   ├── payments.py           ← Partial payment tracker (Bottleneck 5)
│   └── invoices.py           ← Digital invoice generator (Bottleneck 6)
│
└── utils/
    ├── styles.py             ← Global QSS stylesheet / theme
    └── helpers.py            ← Utility functions (currency, dates, IDs)
```

---

##  How to Run

### 1. Install Python
Download Python 3.10+ from https://python.org

### 2. Install dependencies
Open terminal/command prompt in the project folder:
```bash
pip install -r requirements.txt
```

### 3. Configure XAMPP MySQL
This project uses MySQL through `mysql-connector-python`. The included `.env` is already set up for a local XAMPP install:

```powershell
$env:WAREHOUSEIQ_DB_BACKEND="mysql"
$env:WAREHOUSEIQ_DB_HOST="127.0.0.1"
$env:WAREHOUSEIQ_DB_PORT="3307"
$env:WAREHOUSEIQ_DB_USER="root"
$env:WAREHOUSEIQ_DB_PASSWORD=""
$env:WAREHOUSEIQ_DB_NAME="warehouseiq"
```

Start XAMPP MySQL before running the app. If your XAMPP uses port `3306`, the app will fall back to it automatically, or you can edit `.env`.

### 4. Run the app
```bash
python main.py
```

The app will create the `warehouseiq` database and verify its tables during startup.

### Backend API
This repo now also includes a FastAPI backend.

Install dependencies:
```powershell
python -m pip install -r requirements.txt
```

Run the API:
```powershell
python main.py
```

Open Swagger docs:
```text
http://127.0.0.1:8000/docs
```

Inventory endpoints:
```text
GET    /inventory
GET    /inventory/{id}
POST   /inventory
PUT    /inventory/{id}
DELETE /inventory/{id}
```

---

##  Bottleneck → Module Mapping

| # | Bottleneck | Module | How It Solves It |
|---|---|---|---|
| 1 | Slow Warehouse Preparation | `orders.py` | Digital picking list per floor — no running between floors to relay orders |
| 2 | No Real-Time Inventory Visibility | `inventory.py` | Live stock levels checked before committing an order |
| 3 | Insufficient Stocks | `inventory.py` + `orders.py` | Low stock alerts + blocks orders exceeding available qty |
| 4 | Walkie-Talkie Dependency | `orders.py` | Orders relayed digitally from counter to warehouse screen |
| 5 | Manual Partial Payment Tracking | `payments.py` | Per-customer ledger with full payment history |
| 6 | Handwritten Invoices | `invoices.py` | Auto-generated digital invoices with print support |

---

##  Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| PyQt5 | Desktop UI framework |
| MySQL / XAMPP | Local database, accessed through `mysql-connector-python` |
| QPrinter | Invoice printing |

---

##  Git Collaboration Workflow

### 🔽 Get latest updates from GitHub (pull)

Standard way:
```bash
git pull origin main
```

Safer (clean history using rebase):
```bash
git pull origin main --rebase
```

👉 Use this when you want to avoid messy merge commits.

### 🔼 Send your changes to GitHub (push)

Step 1: stage changes
```bash
git add .
```

Step 2: commit changes
```bash
git commit -m "your message here"
```

Step 3: upload to GitHub
```bash
git push origin main
```

### ⚡ Full daily workflow (what you actually use)

Before working (get latest):
```bash
git pull origin main
```

After making changes:
```bash
git add .
git commit -m "update description"
git push origin main
```

---

##  Notes for School Defense
- All operational data is stored in the configured MySQL database (`warehouseiq`)
- The app auto-seeds 10 sample inventory items on first launch
- The system is designed for a **hardware/construction supply store** with a 6-floor warehouse
