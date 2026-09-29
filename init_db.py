import sqlite3

DATABASE = "recipe.db"

# Read schema.sql
with open("database/schema.sql", "r", encoding="utf-8") as file:
    schema = file.read()

# Connect to SQLite database
connection = sqlite3.connect(DATABASE)

# Execute complete schema
connection.executescript(schema)

# Save changes
connection.commit()

# Close connection
connection.close()

print("Database initialized successfully!")