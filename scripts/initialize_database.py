"""Initialize Database tables."""

import sys
from inventory_forecasting.database.session import init_db

if __name__ == "__main__":
    print("Initializing database tables...")
    init_db()
    print("Database tables initialized successfully.")
