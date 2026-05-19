# WarehouseIQ Run Guide

This file is only for running the application.

## What This Project Has

This project currently has two runnable parts:

1. Desktop app
   File: `desktop_main.py`
2. Backend API
   File: `main.py`

## Requirements

Before running anything, make sure you have:

- Python installed
- XAMPP installed
- MySQL/MariaDB running from XAMPP

## Database Settings

The app is currently configured to use XAMPP MySQL through `.env`:

```text
Host: 127.0.0.1
Port: 3307
User: root
Password:
Database: warehouseiq
```

If your XAMPP MySQL is using the default port `3306`, the app will try that automatically when `3307` is not available. You can also edit `.env` and set:

```powershell
$env:WAREHOUSEIQ_DB_PORT="3306"
```

## Open The Correct Folder

In PowerShell:

```powershell
cd C:\Users\micha\Downloads\warehouse_system\warehouseiq-main
```

## Install Dependencies

Use this command:

```powershell
python -m pip install -r requirements.txt
```

If `python` does not work, use:

```powershell
py -m pip install -r requirements.txt
```

## Start XAMPP MySQL

Open XAMPP Control Panel and start:

- `MySQL`

If MySQL is not running, the app will not open correctly.

## Run The Desktop App

Use:

```powershell
python desktop_main.py
```

If needed:

```powershell
py desktop_main.py
```

The desktop app now uses the FastAPI backend instead of connecting to MySQL directly.
If the backend is not already running, `desktop_main.py` will try to start it automatically.

### Desktop Login

Use the default account:

```text
Username: admin
Password: admin123
```

## Run The Backend API

Use:

```powershell
python main.py
```

If needed:

```powershell
py main.py
```

Open the API docs here:

```text
http://127.0.0.1:8000/docs
```

## Run Both At The Same Time

Use two terminals.

Terminal 1:

```powershell
cd C:\Users\micha\Downloads\warehouse_system\warehouseiq-main
python main.py
```

Terminal 2:

```powershell
cd C:\Users\micha\Downloads\warehouse_system\warehouseiq-main
python desktop_main.py
```

This is optional. In normal local use, running only `python desktop_main.py` is usually enough because it can auto-start the backend.

Keep XAMPP MySQL running before opening the app.

## If You Are In The Parent Folder

If you are in:

```text
C:\Users\micha\Downloads\warehouse_system
```

Use:

```powershell
python .\warehouseiq-main\main.py
python .\warehouseiq-main\desktop_main.py
```

## Common Problems

### `requirements.txt` not found

You are probably in the wrong folder.

Fix:

```powershell
cd C:\Users\micha\Downloads\warehouse_system\warehouseiq-main
python -m pip install -r requirements.txt
```

### MySQL access denied

Make sure:

- XAMPP MySQL is running
- it is using port `3307` or `3306`
- the root account allows blank password if you are using the current config

### Desktop app does not open

Run:

```powershell
python desktop_main.py
```

Not:

```powershell
python main.py
```

`main.py` is the backend now.

## Quick Start

If you just want the desktop app:

```powershell
cd C:\Users\micha\Downloads\warehouse_system\warehouseiq-main
python -m pip install -r requirements.txt
python desktop_main.py
```
