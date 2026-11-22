
from db import get_connection


def inspect_database():
    with get_connection() as conn:

        for table_name in ["vendors", "purchase_orders", "tickets", "events"]:
            print(f"\n========== {table_name.upper()} STRUCTURE ==========")

            columns = conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()

            for column in columns:
                print(dict(column))

        print("\n========== INSPECTION COMPLETE ==========")


if __name__ == "__main__":
    inspect_database()
