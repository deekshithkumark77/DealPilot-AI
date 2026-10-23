
from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models


def migrate():
    inspector = inspect(engine)

    existing_tables = inspector.get_table_names()

    if "meeting_notes" not in existing_tables:
        raise RuntimeError(
            "The meeting_notes table was not found. "
            "Stopping to protect the existing database."
        )

    columns = {
        column["name"]
        for column in inspector.get_columns("meeting_notes")
    }

    # Add the new nullable column without deleting existing notes.
    if "deal_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE meeting_notes "
                    "ADD COLUMN deal_id INTEGER "
                    "REFERENCES deals(id)"
                )
            )
        print("Added deal_id to meeting_notes.")
    else:
        print("meeting_notes.deal_id already exists.")

    # Create only missing tables and indexes.
    Base.metadata.create_all(bind=engine)

    print("Database migration completed.")
    print("Existing customer, product, deal, and activity records were preserved.")


if __name__ == "__main__":
    migrate()
