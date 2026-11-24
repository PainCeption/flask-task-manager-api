# Debugging the Task Manager API

This document records concrete problems I encountered while developing the backend. Some happened in the earlier in-memory version and are no longer present in the current source. The final implementation is in [backend/app.py](./backend/app.py) and [backend/database.py](./backend/database.py); the automated checks are in [backend/tests/test_api.py](./backend/tests/test_api.py).

## Validating before accessing request fields

Early on, I tried to read `json_data["title"]` before establishing that the request data was a dictionary and contained `title`. Invalid requests could then raise a Python exception and produce a 500 response instead of the intended client error. I traced the failure back through the task creation route and changed the order of checks: parse the JSON object, check required keys, validate values and supported fields, then create the task. The current `validate_data` and `validate_title` helpers reflect that sequence. I learned that having the right checks is not enough if they run after unsafe access. Flask's parser still handles malformed JSON and incorrect media types before these helpers run.

## Managing IDs in the in-memory version

The first task store was a list of dictionaries. I generated ten-digit IDs with `randint()`, then realized random generation alone could repeat an existing value. A `used_ids` set and retry loop made that temporary scheme safer. I also had to check that each generated value was assigned to the correct task dictionary. When I moved to SQLite, the `tasks.id INTEGER PRIMARY KEY` replaced this manual mechanism. The current API returns database-generated integer IDs; the ten-digit scheme describes an earlier stage only.

## Getting partial updates right

`PATCH` exposed a difference between creating a task and changing one. My first approach assumed every task field would be present, which could fail when a client sent only `{"completed": false}`. I changed the update route to reject an empty object, validate only supplied fields, and pass only those fields to `modify_task`. The database update leaves other columns intact. I learned to test key presence rather than truthiness: `false` is a legitimate value, not evidence that the field was omitted.

## Interpreting an empty response during manual testing

After deleting the last task in the in-memory version, I confirmed that requesting its ID returned 404. A subsequent PowerShell request for the whole collection appeared to show nothing, which initially made me suspect the GET or delete logic. The collection was simply empty, and the terminal presentation was misleading. The current `GET /api/tasks` returns an empty JSON array, `[]`, when the authenticated user has no matching tasks. I learned to inspect the status, content type, and raw response body before treating missing terminal output as an API failure.

## Converting query strings and combining filters

While adding completion filtering, I had to account for `completed=false` arriving as the string `"false"`. Treating that string as a Python boolean would make it truthy. The final `get_task` route explicitly accepts lowercase `"true"`, lowercase `"false"`, or an omitted value. These represent completed tasks, incomplete tasks, and no completion filter. Any other value produces 400.

For categories, reading one query parameter would lose repeated values. I used `request.args.getlist("category")`, then built a parameterized SQL `IN` condition in `fetch_tasks`. The intended combination is any supplied category **and**, when present, the selected completion state. Manual requests helped me examine one filter at a time and then their combination. The current pytest suite directly checks one-category filtering and `completed=true`; it does not directly test repeated categories or combined filters.

## Checking whether edited code was actually running

Several confusing responses during development came from source changes that I had not saved. One case arose while testing task creation, retrieval, and filtering. Another was more alarming: a task created while I expected user ID 3 appeared to belong to user ID 1. I traced the user ID from the JWT through the create route toward the database insert before discovering that the running application still used an older `app.py`. Saving the file resolved the discrepancy. The current route obtains `get_jwt_identity()` and passes that ID to `insert_task`; the database stores it as `user_id`. These episodes taught me to check the saved file and running process before assuming a cross-layer bug.

## Repairing the deletion SQL

During the SQLite migration, I wrote `DETELE` instead of `DELETE` and referred to a `task_id` column that did not exist. I checked the statement against the actual `tasks` schema, whose primary key column is `id`. The final `remove_task` query is:

```sql
DELETE FROM tasks WHERE id = ? AND user_id = ?
```

This fixed both the SQL syntax and the column reference while retaining an ownership condition. I learned to check syntax and schema names separately and to keep request values in parameters.

## Handling SQLite values and transactions

SQLite stores `completed` as `0` or `1`, while the API should return JSON `false` or `true`. I converted the value with `bool()` in both `fetch_tasks` and `fetch_task_by_id`. Filtering sends the corresponding Python boolean as a query parameter, which SQLite can compare with the stored integer. This made the storage format an internal detail rather than part of the response contract.

Database functions also repeated connection, commit, rollback, and close logic during development. I introduced the `database_connection` context manager to handle those steps consistently: it commits after successful work, rolls back an exception, and closes in `finally`. Its `get_connection` helper also enables foreign keys. Centralizing this code reduced the number of places where I had to diagnose resource or transaction mistakes.

## Distinguishing authentication from ownership

JWT protection establishes which user is making a request, but it does not by itself restrict which task that user can access. I checked the path from token identity to every task query. The final `fetch_tasks` filters by `user_id`; `fetch_task_by_id`, `modify_task`, and `remove_task` each require both the task ID and authenticated user ID. An absent or unowned task therefore produces 404 for individual operations. The cross-user pytest test checks read, update, and delete attempts and confirms that the owner's original task remains available.

## Separating backend failures from frontend integration

During team integration discussions, the frontend consisted primarily of static HTML and CSS. Although the visual interface had been developed, its controls and hardcoded tasks were not connected to the API, and JWT authentication had not been integrated.

Manual HTTP requests were used to verify that the backend operated independently. We identified JavaScript `fetch()` calls as a suitable way to connect the frontend to the existing API endpoints, enabling dynamic task management and authenticated requests.

A server-rendered approach using Flask was also considered, but we decided to preserve the existing REST API architecture rather than restructure a functional backend to accommodate the frontend's current limitations.

Ultimately, we agreed to postpone frontend integration until the frontend developer had acquired the necessary JavaScript knowledge.

This experience highlighted the importance of understanding the responsibilities of each application component, identifying missing integration requirements, and communicating technical dependencies within a development team.

## Reproducing and checking fixes

I used PowerShell HTTP requests during development to compare expected and actual statuses and bodies for valid and invalid input, CRUD operations, filters, and authentication. After the main functionality was built, pytest made those checks repeatable. The current suite contains 19 tests, and its [fixture](./backend/tests/conftest.py) gives each test a temporary SQLite database and a test JWT secret. The development history records 19 passing tests at the end of the original development period. I do not claim that every manual scenario is covered by the suite: repeated and combined filters, `completed=false`, and several update validation branches are examples without direct tests.

My useful sequence when a request behaved unexpectedly was to reproduce it, record the status and body, confirm the edited code was saved and running, then trace the input through validation, the route, and the SQL operation. That helped me distinguish application defects from client display behavior, outdated code, storage representation, and missing frontend integration.
