# utils/helpers.py

import datetime
import random
import string

def generate_order_number():
    """Generate a unique order number like ORD-20240101-AB12"""
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    suffix   = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ORD-{date_str}-{suffix}"

def generate_invoice_number():
    """Generate a unique invoice number like INV-20240101-AB12"""
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    suffix   = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INV-{date_str}-{suffix}"

def format_currency(amount):
    """Format a float to Philippine Peso string."""
    return f"₱{amount:,.2f}"

def format_date(dt_string):
    """Format a datetime string to readable format."""
    try:
        dt = datetime.datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y %I:%M %p")
    except:
        return dt_string

def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
