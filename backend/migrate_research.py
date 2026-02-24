
import sqlite3
from typing import List

DB_PATH = "backend/disruptopia.db"

def migrate():
    print(f"Migrating {DB_PATH} for Research Cards...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add columns to players
    columns = [
        ("temp_model_cost_worker_reduction", "INTEGER DEFAULT 0"),
        ("temp_card_cost_worker_reduction", "INTEGER DEFAULT 0"),
        ("temp_compute_monetary_discount", "INTEGER DEFAULT 0"),
        ("temp_compute_gain_power_bonus", "INTEGER DEFAULT 0"),
        ("temp_train_model_per_region_power_bonus", "BOOLEAN DEFAULT 0"),
        ("temp_piggyback_competitor_model", "BOOLEAN DEFAULT 0")
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to players.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in players.")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
