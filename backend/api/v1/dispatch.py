# Owns version 1 dispatch API endpoints.

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from mysql.connector import Error

from backend.domains.shipments.schemas import PickStatusUpdate
from database.connection import get_connection


router = APIRouter(prefix="/dispatch", tags=["Dispatch"])


class DispatchHub:
    def __init__(self):
        self.connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, payload):
        stale = []
        for websocket in self.connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


dispatch_hub = DispatchHub()


def _floor_groups(items):
    grouped = defaultdict(list)
    for item in items:
        grouped[int(item.get("floor") or 1)].append(item)
    return [
        {"floor": floor, "items": grouped[floor], "count": len(grouped[floor])}
        for floor in sorted(grouped)
    ]


def _order_payload(cursor, order):
    cursor.execute(
        """
        SELECT oi.id AS order_item_id, oi.item_id, i.item_code, i.item_name, i.category,
               i.floor, oi.quantity, oi.unit_price, oi.pick_status, oi.picked_quantity
        FROM order_items oi
        JOIN inventory i ON oi.item_id = i.id
        WHERE oi.order_id = ?
        ORDER BY i.floor ASC, i.item_name ASC
        """,
        (order["id"],),
    )
    items = cursor.fetchall()
    return {**order, "items": items, "floor_groups": _floor_groups(items)}


@router.get("/queue")
def get_dispatch_queue(status_filter: Optional[str] = None):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = """
            SELECT *
            FROM orders
            WHERE status IN ('Pending', 'Processing', 'Ready', 'Completed')
        """
        params = []
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, tuple(params))
        return [_order_payload(cursor, order) for order in cursor.fetchall()]
    except Error as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dispatch queue: {exc}") from exc
    finally:
        cursor.close()
        connection.close()


@router.put("/{order_id}/items/{item_id}")
async def update_pick_status(order_id: int, item_id: int, payload: PickStatusUpdate):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, quantity
            FROM order_items
            WHERE order_id = ? AND item_id = ?
            """,
            (order_id, item_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dispatch item not found")
        picked_quantity = payload.picked_quantity
        if picked_quantity is None:
            picked_quantity = row["quantity"] if payload.status == "Picked" else 0
        cursor.execute(
            """
            UPDATE order_items
            SET pick_status = ?, picked_quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.status, picked_quantity, row["id"]),
        )
        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN pick_status = 'Picked' THEN 1 ELSE 0 END) AS picked,
                   SUM(CASE WHEN pick_status = 'Out of Stock' THEN 1 ELSE 0 END) AS missing
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        )
        counts = cursor.fetchone()
        order_status = "Processing"
        if counts["total"] and counts["picked"] == counts["total"]:
            order_status = "Ready"
        elif counts["missing"]:
            order_status = "Processing"
        cursor.execute(
            """
            UPDATE orders
            SET status = ?, dispatch_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (order_status, order_status, order_id),
        )
        cursor.execute(
            """
            INSERT INTO audit_log (actor, action, entity_type, entity_id, new_value)
            VALUES (?, 'pick-status', 'order_item', ?, ?)
            """,
            (payload.actor, row["id"], payload.status),
        )
        connection.commit()
        update = {"type": "dispatch_update", "order_id": order_id, "item_id": item_id, "status": payload.status}
    except HTTPException:
        connection.rollback()
        raise
    except Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update pick status: {exc}") from exc
    finally:
        cursor.close()
        connection.close()
    try:
        await dispatch_hub.broadcast(update)
    except Exception:
        pass
    return {"message": "Pick status updated", **update}


@router.websocket("/ws")
async def dispatch_websocket(websocket: WebSocket):
    await dispatch_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dispatch_hub.disconnect(websocket)
