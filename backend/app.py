from flask import Flask, request, abort
import database
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]

jwt = JWTManager(app)
database.initialize_database()

accepted_keys = {"title", "description", "category", "completed"}
boolean_keys = {"true": True, "false": False, None: None}
required_keys = ["username", "password"]

# register a user
@app.route("/api/register", methods=["POST"])
def register():
    json_data = validate_data()
    validate_username_password(json_data)

    password = json_data["password"]
    password_hash = generate_password_hash(password)
    try:
        new_user_id = database.insert_user(json_data["username"], password_hash)
    except sqlite3.IntegrityError:
        abort(409, description="Username already exists")

    new_user = {"id": new_user_id, "username": json_data["username"]}
    return new_user, 201

# login the user, username and password must match
@app.route("/api/login", methods=["POST"])
def login():
    json_data = validate_data()
    validate_username_password(json_data)
    user = database.fetch_user_by_username(json_data["username"])
    if user is None:
        abort(401, description="Invalid username or password")
    if not check_password_hash(user["password_hash"], json_data["password"]):
        abort(401, description="Invalid username or password")

    access_token = create_access_token(identity=str(user["id"]))

    return {"message": "Login successful", "access_token": access_token}, 200

# get task, includes the ability to get tasks based on category and completed status
# only allows user who created the task to be able to view this task
@app.route("/api/tasks")
@jwt_required()
def get_task():
    user_id = int(get_jwt_identity())
    categories = request.args.getlist("category")
    completed = request.args.get("completed")
    if completed not in boolean_keys:
        abort(400, description="Expected a valid completed status")

    user_tasks = database.fetch_tasks(
        user_id,
        categories,
        boolean_keys[completed]
    )

    return user_tasks
# create a task. adds empty category, description and also defaults completed into false if not
# provided by the user
@app.route("/api/tasks", methods=["POST"])
@jwt_required()
def create_task():
    user_id = int(get_jwt_identity())
    json_data = validate_data()
    if "title" not in json_data:
        abort(400, description="Expected a task title")
    validate_title(json_data["title"])

    validate_keys(json_data)
    for key in accepted_keys:
        if key not in json_data:
            if key == "completed":
                json_data["completed"] = False
                continue
            json_data[key] = ""

    validate_string(json_data["description"])
    validate_string(json_data["category"])
    validate_bool(json_data["completed"])

    new_id = database.insert_task(
        json_data["title"],
        json_data["description"],
        json_data["category"],
        json_data["completed"],
        user_id
    )

    new_task = database.fetch_task_by_id(new_id, user_id)
    if new_task is None:
        abort(500, description="Created task could not be retrieved")

    return new_task, 201

# updates a task. if no task was found cause it doesnt exist or wrong user, error 404
@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@jwt_required()
def update_task(task_id: int):
    user_id = int(get_jwt_identity())
    json_data = validate_data()
    if not json_data:
        abort(400, description="Expected at least one field to update")
    validate_keys(json_data)

    for key in json_data:
        if key == "title":
            validate_title(json_data["title"])
            continue
        if key == "completed":
            validate_bool(json_data["completed"])
            continue
        validate_string(json_data[key])

    affected_rows = database.modify_task(task_id, user_id, json_data)

    if affected_rows == 0:
        abort(404, description="Expected task to exist")

    return get_task_by_id(task_id)

# deletes a task. return 204 code to message that process was completed
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id: int):
    user_id = int(get_jwt_identity())
    deleted_rows = database.remove_task(task_id, user_id)
    if deleted_rows == 0:
        abort(404, description="Expected task to exist")
    return "", 204

# get task using task id, functions as a helper as well
@app.route("/api/tasks/<int:task_id>")
@jwt_required()
def get_task_by_id(task_id: int):
    user_id = int(get_jwt_identity())
    task = database.fetch_task_by_id(task_id, user_id)
    if task is None:
        abort(404, description="Expected task to exist")
    return task

# validation helper functions below
def validate_data():
    json_data = request.get_json()
    if not isinstance(json_data, dict):
        abort(400, description="Expected dictionary data type")
    return json_data   

def validate_title(title: str, field="title"):
    if not isinstance(title, str):
        abort(400, description=f"Expected a string value for {field}")
    if not title.strip():
        abort(400, description=f"Expected {field} to not be empty")

def validate_string(string: str):
    if not isinstance(string, str):
        abort(400, description="Expected a string value")

def validate_keys(data):
    for key in data:
        if key not in accepted_keys:
            abort(400, description="Expected valid key")

def validate_bool(boolean: bool):
    if not isinstance(boolean, bool):
        abort(400, description="Expected a boolean value")

def validate_username_password(data):
    for key in required_keys:
        if key not in data:
            abort(400, description="Expected valid keys")
    validate_title(data["username"], "username")
    validate_title(data["password"], "password")