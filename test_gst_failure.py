
from unittest.mock import patch

from app.tools import gst_check


def test_gst_database_failure():
    print("\nTesting GST tool database failure...")

    with patch(
        "app.tools.get_connection",
        side_effect=Exception("Simulated database connection failure")
    ):
        result = gst_check("09ABCDE1234F1Z5")

    print("GST Tool Result:", result)

    assert result["valid"] is False
    assert result["reason"] == "GST tool error"

    print("PASS: GST tool failed safely.")


if __name__ == "__main__":
    test_gst_database_failure()
    print("\nGST tool failure test completed successfully.")
