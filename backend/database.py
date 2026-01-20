from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base  # Importing the Base class you defined

# 1. Define the Database URL
# This creates a file named 'disruptopia.db' in your backend folder
SQLALCHEMY_DATABASE_URL = "sqlite:///./disruptopia.db"

# 2. Create the Engine
# 'check_same_thread' is only needed for SQLite to allow multi-user access
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Create a Session Factory
# This allows us to create 'instances' of database connections
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    This function creates the tables in the SQLite file.
    It reads the 'Base' metadata from models.py.
    """
    print("Initializing the Disruptopia database...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    init_db()