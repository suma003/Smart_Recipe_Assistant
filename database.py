import sqlite3

DATABASE = "recipe.db"

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    # Dictionary-এর মতো কলামের নামে ডাটা অ্যাক্সেস করার জন্য:
    connection.row_factory = sqlite3.Row

    # SQLite disables foreign key enforcement by default, on every
    # new connection. Our schema.sql defines FOREIGN KEY constraints
    # (e.g. ON DELETE CASCADE for Recipes -> Recipe_Ingredients,
    # Favorites, Ratings, Comments, etc.), but without this PRAGMA
    # those constraints are silently ignored and never enforced.
    # This line must run on every connection (SQLite does not
    # remember this setting between connections).
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
