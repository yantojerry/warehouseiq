# Owns version 1 invoice API endpoints.

import datetime
from html import escape
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlite3 import Error

from database.connection import get_connection
from backend.core.helpers import generate_invoice_number
from ui.theme import COLORS, FONT_FALLBACK, FONT_MONO


router = APIRouter(prefix="/invoices", tags=["Invoices"])


class InvoiceCreate(BaseModel):
    customer_id: Optional[int] = None
    customer_name: str = Field(..., min_length=1, max_length=255)
    total_amount: float = Field(..., gt=0)
    amount_paid: float = Field(default=0.0, ge=0)
    payment_method: Optional[str] = Field(default=None, max_length=50)
    order_id: Optional[int] = None
    invoice_number: Optional[str] = Field(default=None, max_length=50)


class InvoiceCancel(BaseModel):
    reason: str = Field(..., min_length=1)
    actor: Optional[str] = "system"


def _invoice_status(total, paid):
    total_value = float(total or 0)
    paid_value = float(paid or 0)
    if total_value <= 0:
        return "Pending"
    if paid_value >= total_value:
        return "Paid"
    if paid_value > 0:
        return "Partial"
    return "Unpaid"


@router.get("")
def list_invoices(
    search: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT i.id, i.invoice_number, i.customer_name, o.order_number,
                   i.total_amount, i.amount_paid, i.payment_method, i.status, i.issued_at
            FROM invoices i
            LEFT JOIN orders o ON i.order_id = o.id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (i.customer_name LIKE ? OR i.invoice_number LIKE ? OR i.issued_at LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        if status_filter and status_filter != "All":
            query += " AND i.status = ?"
            params.append(status_filter)
        query += " ORDER BY i.issued_at DESC"
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate):
    invoice_number = payload.invoice_number or generate_invoice_number()
    invoice_status = _invoice_status(payload.total_amount, payload.amount_paid)
    connection = get_connection()
    cursor = connection.cursor()
    try:
        customer_id = payload.customer_id
        if customer_id is None:
            cursor.execute("SELECT id FROM customers WHERE full_name = ? LIMIT 1", (payload.customer_name,))
            customer = cursor.fetchone()
            if customer:
                customer_id = customer[0] if not isinstance(customer, dict) else customer.get("id")
        cursor.execute(
            """
            INSERT INTO invoices (
                invoice_number, order_id, customer_id, customer_name, total_amount,
                amount_paid, payment_method, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_number,
                payload.order_id,
                customer_id,
                payload.customer_name,
                payload.total_amount,
                payload.amount_paid,
                payload.payment_method,
                invoice_status,
            ),
        )
        connection.commit()
        return {
            "message": "Invoice created successfully",
            "id": cursor.lastrowid,
            "invoice_number": invoice_number,
        }
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT i.*, o.order_number
            FROM invoices i
            LEFT JOIN orders o ON i.order_id = o.id
            WHERE i.id = ?
            """,
            (invoice_id,),
        )
        invoice = cursor.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoice: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.post("/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, payload: InvoiceCancel):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        invoice = cursor.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.get("status") == "Cancelled":
            raise HTTPException(status_code=400, detail="Invoice is already cancelled")
        cursor.execute(
            """
            UPDATE invoices
            SET status = 'Cancelled',
                cancel_reason = ?,
                cancelled_by = ?,
                cancelled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.reason, payload.actor, invoice_id),
        )
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, reason, old_value, new_value)
            VALUES (?, 'cancel', 'invoice', ?, ?, ?, 'Cancelled')
            """,
            (payload.actor, invoice_id, payload.reason, invoice.get("status")),
        )
        connection.commit()
        return {"message": "Invoice cancelled", "id": invoice_id}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel invoice: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.get("/{invoice_id}/html", response_class=HTMLResponse)
def get_invoice_html(invoice_id: int):
    return build_invoice_html(invoice_id)


def build_invoice_html(invoice_id: int):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT i.*, o.order_number
            FROM invoices i
            LEFT JOIN orders o ON i.order_id = o.id
            WHERE i.id = ?
            """,
            (invoice_id,),
        )
        invoice = cursor.fetchone()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        items_html = ""
        if invoice["order_id"]:
            cursor.execute(
                """
                SELECT it.item_name, oi.quantity, oi.unit_price,
                       (oi.quantity * oi.unit_price) AS subtotal
                FROM order_items oi
                JOIN inventory it ON oi.item_id = it.id
                WHERE oi.order_id = ?
                """,
                (invoice["order_id"],),
            )
            for item in cursor.fetchall():
                items_html += f"""
                <tr>
                    <td>{escape(str(item['item_name']))}</td>
                    <td style='text-align:center;'>{item['quantity']}</td>
                    <td style='text-align:right;'>{item['unit_price']:,.2f}</td>
                    <td style='text-align:right;'>{item['subtotal']:,.2f}</td>
                </tr>"""

        balance = float(invoice["total_amount"] - invoice["amount_paid"])
        date_str = datetime.datetime.now().strftime("%B %d, %Y")
        payment_method = invoice.get("payment_method") or "Not specified"
        order_label = ""
        if invoice["order_number"]:
            order_label = (
                f"<span style=\"color:{COLORS['text_3']};font-size:12px;\">"
                f"Order: {escape(str(invoice['order_number']))}</span>"
            )
        no_items = (
            f"<tr><td colspan='4' style='text-align:center;color:{COLORS['text_3']};'>"
            "No items</td></tr>"
        )

        return f"""
        <html><head><style>
            body {{ font-family: {FONT_FALLBACK}, sans-serif; margin: 40px; color: {COLORS['text']}; }}
            .header {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
            .company {{ font-size: 22px; font-weight: bold; color: {COLORS['navy']}; }}
            .accent {{ color: {COLORS['teal_light']}; }}
            .invoice-title {{ font-size: 28px; font-weight: bold; color: {COLORS['text_2']}; text-align: right; }}
            .invoice-num {{ font-family: {FONT_MONO}, monospace; font-size: 14px; color: {COLORS['navy']}; text-align: right; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: {COLORS['surface']}; padding: 10px; text-align: left; font-size: 13px; }}
            td {{ padding: 10px; border-bottom: 1px solid {COLORS['border']}; font-size: 13px; }}
            .totals td {{ border: none; font-weight: bold; }}
            .balance {{ color: {COLORS['red']}; font-size: 16px; }}
            .paid-stamp {{ color: {COLORS['teal']}; font-size: 24px; font-weight: bold; border: 3px solid {COLORS['teal']};
                           display: inline-block; padding: 4px 16px; border-radius: 4px; transform: rotate(-10deg); }}
        </style></head><body>
            <div class='header'>
                <div>
                    <div class='company'>MIHS <span class='accent'>General Merchandise</span></div>
                    <div style='color:{COLORS['text_3']};font-size:12px;'>Digital invoice backup</div>
                </div>
                <div>
                    <div class='invoice-title'>INVOICE</div>
                    <div class='invoice-num'>{escape(str(invoice['invoice_number']))}</div>
                    <div style='text-align:right;font-size:12px;color:{COLORS['text_3']};'>{date_str}</div>
                </div>
            </div>
            <div style='margin-bottom:20px;'>
                <b>Bill To:</b><br>
                <span style='font-size:15px;'>{escape(str(invoice['customer_name']))}</span><br>
                {order_label}
            </div>
            <div style='margin-bottom:12px;color:{COLORS['text_2']};font-size:13px;'>
                <b>Payment Method:</b> {escape(str(payment_method))}
            </div>
            <table>
                <thead><tr><th>Item</th><th style='text-align:center;'>Qty</th>
                <th style='text-align:right;'>Unit Price</th><th style='text-align:right;'>Subtotal</th></tr></thead>
                <tbody>{items_html if items_html else no_items}</tbody>
            </table>
            <table style='width:40%;margin-left:60%;'>
                <tr class='totals'><td>Total:</td><td style='text-align:right;'>PHP {invoice['total_amount']:,.2f}</td></tr>
                <tr class='totals'><td>Amount Paid:</td><td style='text-align:right;color:{COLORS['teal']};'>PHP {invoice['amount_paid']:,.2f}</td></tr>
                <tr class='totals'><td class='balance'>Balance Due:</td><td style='text-align:right;' class='balance'>PHP {balance:,.2f}</td></tr>
            </table>
            {'<div style="margin-top:20px;"><span class="paid-stamp">FULLY PAID</span></div>' if balance <= 0 else ''}
            <div style='margin-top:40px;border-top:1px solid {COLORS['border']};padding-top:12px;font-size:11px;color:{COLORS['text_3']};'>
                This is a computer-generated invoice with a recoverable digital trail.
            </div>
        </body></html>
        """
    except HTTPException:
        raise
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build invoice HTML: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
