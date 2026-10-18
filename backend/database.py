
import sqlite3
from pathlib import Path
from contextlib import contextmanager

allowed_keys = {"title", "description", "category", "completed"}
DB_PATH = Path(__file__).resolve().parent / "tasks.db"


# connection helper
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        return connection
    except Exception:
        connection.close()
        raise


# helper for any errors that could happen, and making sure we rollback and/or close the connection
@contextmanager
def database_connection():
    connection = get_connection()

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# create or connect to the tables
def initialize_database():
    with database_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


# creating a user
def insert_user(username, password_hash):
    with database_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        new_user_id = cursor.lastrowid

    return new_user_id


# fetch a user with username
def fetch_user_by_username(username):
    with database_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        user = cursor.fetchone()

        if user is None:
            return None

        return dict(user)


# creation of a task
def insert_task(title, description, category, completed, user_id):
    with database_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, description, category, completed, user_id) VALUES (?, ?, ?, ?, ?)",
            (title, description, category, completed, user_id)
        )
        new_id = cursor.lastrowid

    return new_id


# fetch a task using user id and category/completed statuses
def fetch_tasks(user_id, categories=None, completed=None):
    sql = "SELECT * FROM tasks WHERE user_id = ?"
    values = [user_id]

    if categories:
        placeholders = []
        for i in range(len(categories)):
            placeholders.append("?")

        placeholders = ", ".join(placeholders)
        sql += f" AND category IN ({placeholders})"
        values += categories

    if completed is not None:
        sql += " AND completed = ?"
        values.append(completed)

    with database_connection() as connection:
        cursor = connection.execute(sql, values)
        rows = cursor.fetchall()

        new_list = []
        for row in rows:
            task = dict(row)
            task["completed"] = bool(task["completed"])
            new_list.append(task)

        return new_list


# fetch a task using the id and user id. u end up returning a specific task or None
def fetch_task_by_id(task_id, user_id):
    with database_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )

        task = cursor.fetchone()

        if task is None:
            return None

        task = dict(task)
        task["completed"] = bool(task["completed"])
        return task


# update a task
def modify_task(task_id, user_id, data):
    if not data:
        raise ValueError("Empty dictionary")

    key_parts = []
    value_parts = []

    for key, value in data.items():
        if key not in allowed_keys:
            raise ValueError("Invalid key")

        key_parts.append(f"{key} = ?")
        value_parts.append(value)

    set_string = ", ".join(key_parts)
    sql = f"UPDATE tasks SET {set_string} WHERE id = ? AND user_id = ?"
    value_parts += (task_id, user_id)

    with database_connection() as connection:
        cursor = connection.execute(sql, value_parts)
        affected_rows = cursor.rowcount

    return affected_rows


# delete a task
def remove_task(task_id, user_id):
    with database_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        deleted_rows = cursor.rowcount

    return deleted_rows
