
from db import get_connection, init_db


def seed_data():
    init_db()

    with get_connection() as conn:

        # Sample vendor
        conn.execute("""
            INSERT OR REPLACE INTO vendors
            (gstin, name, active)
            VALUES (?, ?, ?)
        """, (
            "09ABCDE1234F1Z5",
            "ABC Traders",
            1
        ))

        # Sample purchase order
        conn.execute("""
            INSERT OR REPLACE INTO purchase_orders
            (po_id, vendor, amount)
            VALUES (?, ?, ?)
        """, (
            "PO-2207",
            "ABC Traders",
            12000
        ))

        conn.commit()

    print("Sample vendor and purchase order inserted successfully.")


if __name__ == "__main__":
    seed_data()
