import os
import sqlite3

# Use persistent path on Render if available.
# Otherwise use local project folder.
DATABASE = os.environ.get("DATABASE_PATH", "recipe.db")


def get_db_connection():
    connection = sqlite3.connect(DATABASE)

    # Access columns by name
    connection.row_factory = sqlite3.Row

    # Enable foreign key constraints
    connection.execute("PRAGMA foreign_keys = ON")

    return connection