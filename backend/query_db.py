# This file is just for debugging, FYI.
from backend.database import SessionLocal
from backend.models import Component, Player

db = SessionLocal()

# Check how many cards are in the decks
count = db.query(Component).count()
print(f"Total components: {count}")

# Look at the specific cards we seeded
cards = db.query(Component).all()
for c in cards:
    print(f"ID: {c.id} | Name: {c.name} | Zone: {c.zone} | Type: {c.sub_type}")

db.close()
exit()