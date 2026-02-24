
import sqlite3
from typing import List

DB_PATH = "backend/disruptopia.db"

def migrate():
    print(f"Migrating {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Add columns to card_details
    columns_to_add = [
        ("description", "TEXT"),
        ("requirements", "TEXT"),
        ("image_file", "TEXT")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE card_details ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to card_details.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists in card_details.")
            else:
                print(f"Error adding {col_name}: {e}")

    # 2. Add columns to players
    try:
        cursor.execute("ALTER TABLE players ADD COLUMN workers_spent_on_cards INTEGER DEFAULT 0")
        print("Added column workers_spent_on_cards to players.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Column workers_spent_on_cards already exists in players.")
        else:
            print(f"Error adding workers_spent_on_cards: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
