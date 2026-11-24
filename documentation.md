# Task Manager API: development process

I developed the backend of this project as part of a team building a task manager. Other team members worked on the frontend. My goal was to build a Flask API that could store each user's tasks, authenticate requests, and give the frontend a clear HTTP interface. This document records how the backend evolved and what I learned from the decisions along the way. The [README](./README.md) contains setup instructions and a compact API reference.

## 1. Establishing the API with in-memory data

I began with Flask routes and a Python list of task dictionaries. This let me learn how route decorators map URLs and HTTP methods to functions, how to read JSON request bodies, and how to return data and status codes before adding SQL. The early version generated ten-digit task IDs and tracked used IDs in a set. It supported basic task creation, retrieval, updating, and deletion, but its data disappeared when the process restarted. Those identifiers and the list-based storage belong to the development history; the current implementation uses SQLite-generated integer IDs.

Working on the HTTP interface first clarified the separation between the frontend and backend. A client sends requests to endpoints; it does not call Python functions directly. I also learned to distinguish a task ID in the URL from filters in the query string and fields in a JSON body.

## 2. Defining task behavior before persistence

The task resource settled on `title`, `description`, `category`, and `completed`. Creation requires a nonempty string title. When omitted, `description` and `category` become empty strings and `completed` becomes `false`. I extracted validation into `validate_data`, `validate_title`, `validate_string`, `validate_keys`, and `validate_bool` in [backend/app.py](./backend/app.py). Task creation and updates accept only those four task fields; descriptions and categories must be strings, and completion must be a JSON boolean. Whitespace-only titles are rejected, although a title with surrounding whitespace is not trimmed before storage.

I chose `PATCH` for partial changes so a client can update one field without resending the whole task. The handler rejects an empty object, validates each supplied field, and preserves omitted fields. Checking whether a key is present matters here: `false` is a valid value for `completed`, even though it is falsey in Python.

Filtering was first explored with Python collections, then moved into the database query. `GET /api/tasks` accepts repeated `category` parameters and an optional `completed=true` or `completed=false` parameter. Repeated categories match any selected category; a completion filter further narrows the result. Query parameters arrive as strings, so the implementation explicitly maps the lowercase strings `true` and `false` to booleans and rejects other completion values with HTTP 400.

## 3. Moving to SQLite

Once the task interface worked, I replaced the temporary list with a dedicated database module in [backend/database.py](./backend/database.py). SQLite gave the project persistent relational storage without a separate database server. The application initializes the schema when [backend/app.py](./backend/app.py) is imported; its database path is `backend/tasks.db`. Runtime database files are excluded from Git.

The schema has two tables:

| Table | Stored fields and constraints |
| --- | --- |
| `users` | Integer primary key `id`, unique non-null `username`, and non-null `password_hash` |
| `tasks` | Integer primary key `id`; non-null `title`, `description`, and `category`; integer `completed` with default `0` and a `0`/`1` check; non-null `user_id` referencing `users.id` |

One user can own many tasks, while each task has one owner. Connections enable SQLite foreign keys and return rows through `sqlite3.Row`. The `database_connection` context manager commits successful operations, rolls back exceptions, and closes the connection. This kept connection and transaction handling outside the route functions.

Database operations use parameterized values rather than interpolating client data into SQL. For optional task filters, `fetch_tasks` adds placeholders for selected categories and completion status. For updates, `modify_task` builds column names only after checking them against an allowlist. Rows are converted to dictionaries, and SQLite's stored `0`/`1` completion values are converted back to JSON booleans.

## 4. Adding accounts and access control

After introducing the user table, I added registration and login. Both endpoints require a JSON object with nonempty string `username` and `password` values. Registration hashes the password with Werkzeug before calling `insert_user`; a duplicate username produces HTTP 409. Login retrieves the user by username, checks the supplied password against the hash, and returns a JWT access token on success. Invalid credentials produce HTTP 401. The code does not define a password-strength policy or reject extra account fields, so I do not treat either as implemented validation.

Flask-JWT-Extended protects every task route. The client supplies `Authorization: Bearer <access_token>`, and the application reads the user ID from the token. `JWT_SECRET_KEY` must come from the environment. I learned that authentication identifies the caller, while authorization still requires checking which records that caller may use.

The database enforces that distinction in its task queries. `insert_task` assigns the authenticated user as owner. `fetch_tasks` limits the collection to that user. `fetch_task_by_id`, `modify_task`, and `remove_task` all constrain operations by both task ID and user ID. Consequently, a request for another user's task receives the same HTTP 404 as a request for an absent task. Clients cannot choose or change `user_id` through task input.

## 5. The resulting HTTP interface

| Method and path | Result on success |
| --- | --- |
| `POST /api/register` | Creates a user and returns its ID and username (`201`) |
| `POST /api/login` | Returns an access token (`200`) |
| `GET /api/tasks` | Returns the authenticated user's tasks, optionally filtered (`200`) |
| `POST /api/tasks` | Creates and returns an owned task (`201`) |
| `GET /api/tasks/<int:task_id>` | Returns one owned task (`200`) |
| `PATCH /api/tasks/<int:task_id>` | Updates supplied fields and returns the task (`200`) |
| `DELETE /api/tasks/<int:task_id>` | Deletes an owned task with an empty response (`204`) |

Task responses include `id`, the four task fields, and `user_id`. The routes use HTTP 400 for the invalid task input they explicitly check, 401 for failed login or missing task authentication, 404 for missing or unowned tasks, and 409 for duplicate usernames. There is no custom JSON error handler in the current code: ordinary Flask `abort()` errors use Flask's default error response, while JWT errors are handled by Flask-JWT-Extended. The successful resource responses are JSON.

## 6. Testing and collaboration

The repository contains 19 pytest test functions in [backend/tests/test_api.py](./backend/tests/test_api.py). A fixture in [backend/tests/conftest.py](./backend/tests/conftest.py) sets a test JWT secret, redirects database operations to a fresh temporary SQLite file for each test, initializes the tables, and uses Flask's test client. This keeps the tests away from the normal runtime database.

The tests cover registration and duplicate names; successful and failed login; authentication on task listing and creation; task creation, retrieval, updating, and deletion; one-category and `completed=true` filters; selected invalid creation inputs; and task isolation between two users. The cross-user test checks read, update, and delete attempts and confirms the owner's task remains intact. The development history records 19 passing tests at the end of the main development period, and the current test file contains 19 test functions.

The suite does not directly test every branch: examples include repeated category filters, combined filters, `completed=false`, empty `PATCH` bodies, invalid update fields, and all unauthenticated item routes. I regard those as coverage limits, not missing endpoints.

During frontend integration discussions, the frontend was primarily HTML and CSS and had not yet been connected to this API. We identified JavaScript `fetch()` requests, token handling, dynamic task display, and error presentation as the work needed for integration. Server-rendered Flask pages were considered, but the preferred direction was to keep the REST API and connect the frontend to it. This repository does not show that frontend integration as completed functionality.

I also learned practical collaboration boundaries: another developer's `localhost` does not point to my running server, GitHub shares committed source rather than a local SQLite database, and secrets and runtime files need to stay out of version control. I used AI for explanations, architectural guidance, and code review while learning unfamiliar parts of Flask, JWTs, and database connection handling. As disclosed in the [README](./README.md), the pytest suite and initial README were generated by AI; reviewing the behavior and understanding the code remained part of my development work.

## Reflection

Building the API in stages helped me understand each new responsibility before combining them. The in-memory version taught me request and response behavior. SQLite introduced durable data and relationships. JWTs made me separate identity from permission, and ownership checks moved that rule into every relevant query. The main lesson was that a usable backend requires coherent validation, persistence, access control, and tests in addition to working routes.
