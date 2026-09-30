import os
import sqlite3

DATABASE = os.environ.get("DATABASE_PATH", "recipe.db")

# Read schema.sql
with open("database/schema.sql", "r", encoding="utf-8") as file:
    schema = file.read()

# Connect to SQLite database
connection = sqlite3.connect(DATABASE)

# Enable foreign keys
connection.execute("PRAGMA foreign_keys = ON")

# Execute schema
connection.executescript(schema)

# Save changes
connection.commit()

# Close connection
connection.close()

print(f"Database initialized successfully: {DATABASE}")