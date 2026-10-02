import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.descope import DescopeProvider
from fastmcp.server.dependencies import get_access_token
from pydantic import BaseModel

load_dotenv()

CONFIG_URL = os.environ["DESCOPE_CONFIG_URL"]
SERVER_URL = os.environ["SERVER_URL"]
BASE_URL = SERVER_URL.removesuffix("/mcp")

auth = DescopeProvider(
    config_url=CONFIG_URL,
    base_url=BASE_URL,
    scopes_supported=["todo:read", "todo:write"],
)

mcp = FastMCP(
    name="Todo",
    instructions=(
        "A simple todo list app. Provides tools: create_todo, list_todos, "
        "get_todo, get_todo_by_title, update_todo and delete_todo."
    ),
    auth=auth,
)


def _current_user(*required_scopes: str) -> str:
    """Return the caller's user id; raise ToolError if unauthenticated or missing scopes."""
    token = get_access_token()
    if token is None:
        raise ToolError("Authentication required")

    missing = [s for s in required_scopes if s not in (token.scopes or [])]
    if missing:
        raise ToolError(f"Missing required scopes: {', '.join(missing)}")

    claims = token.claims or {}
    user_id = claims.get("sub") or claims.get("userId") or token.client_id
    if not user_id:
        raise ToolError("Could not determine user identity")
    return user_id


@mcp.tool()
def whoami() -> dict:
    """Show who the server thinks you are and what you are allowed to do."""
    token = get_access_token()
    if token is None:
        return {"error": "Auth is mandatory"}
    return {
        "user_id": token.claims.get("sub") if token.claims else None,
        "client_id": token.client_id,
        "scopes": token.scopes,
        "expires_at": token.expires_at,
    }


StatusType = Literal["Pending", "Completed", "Deleted"]

STORE_PATH = Path(__file__).with_name("todos.json")
_LOCK = threading.Lock()


class Todo(BaseModel):
    id: str
    owner: str
    title: str
    description: str = ""
    status: StatusType = "Pending"
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load() -> dict[str, Todo]:
    if not STORE_PATH.exists():
        return {}
    raw = json.loads(STORE_PATH.read_text() or "[]")
    for item in raw:
        item.setdefault("owner", "legacy")
    return {item["id"]: Todo.model_validate(item) for item in raw}


def _save(todos: dict[str, Todo]) -> None:
    STORE_PATH.write_text(
        json.dumps([t.model_dump() for t in todos.values()], indent=2) + "\n"
    )


def _get_or_raise(todo_id: str, user_id: str) -> tuple[dict[str, Todo], Todo]:
    todos = _load()
    todo = todos.get(todo_id)
    # Same error for "missing" and "not yours" so ids can't be probed
    if todo is None or todo.owner != user_id:
        raise ToolError(f"Todo with id {todo_id} is not present")
    return todos, todo


@mcp.tool
def create_todo(
    title: Annotated[str, "Short title of the todo"],
    description: Annotated[str, "Optional long description"] = "",
    status: Annotated[StatusType, "Pending, Completed or Deleted"] = "Pending",
) -> Todo:
    """Creates a new todo and returns it"""
    user_id = _current_user("todo:write")

    title = title.strip()
    if not title:
        raise ToolError("Title cannot be empty")

    now = _now()
    todo = Todo(
        id=uuid4().hex[:8],
        owner=user_id,
        title=title,
        description=description.strip(),
        status=status,
        created_at=now,
        updated_at=now,
    )

    with _LOCK:
        todos = _load()
        todos[todo.id] = todo
        _save(todos)

    return todo


@mcp.tool
def list_todos(
    status: Annotated[StatusType | None, "Pending, Completed, Deleted or None for all"] = None,
) -> list[Todo]:
    """Lists your todos, newest first. Optionally filter by status"""
    user_id = _current_user("todo:read")

    with _LOCK:
        todos = [t for t in _load().values() if t.owner == user_id]

    if status is not None:
        todos = [t for t in todos if t.status == status]

    todos.sort(key=lambda t: t.created_at, reverse=True)
    return todos


@mcp.tool
def get_todo(todo_id: Annotated[str, "The ID of the todo to get"]) -> Todo:
    """Get a todo by ID"""
    user_id = _current_user("todo:read")

    with _LOCK:
        _, todo = _get_or_raise(todo_id, user_id)
    return todo


@mcp.tool
def get_todo_by_title(
    todo_title: Annotated[str, "Title (or part of it) of the todo to find"],
) -> Todo | None:
    """Get the first todo whose title partially matches the given text (case-insensitive)"""
    user_id = _current_user("todo:read")

    needle = todo_title.strip().lower()
    if not needle:
        raise ToolError("Title cannot be empty")

    with _LOCK:
        todos = list(_load().values())

    for t in todos:
        if t.owner == user_id and needle in t.title.lower():
            return t
    return None


@mcp.tool
def delete_todo(todo_id: Annotated[str, "ID of the todo to be deleted"]) -> str:
    """Delete a todo by id"""
    user_id = _current_user("todo:write")

    with _LOCK:
        todos, _ = _get_or_raise(todo_id, user_id)
        del todos[todo_id]
        _save(todos)

    return f"Deleted todo with id {todo_id}"


@mcp.tool
def update_todo(
    todo_id: Annotated[str, "ID of todo to be updated"],
    title: Annotated[str | None, "New title (optional)"] = None,
    description: Annotated[str | None, "New description (optional)"] = None,
    status: Annotated[StatusType | None, "Pending, Completed or Deleted (optional)"] = None,
) -> Todo:
    """Update a todo when given its ID"""
    user_id = _current_user("todo:write")

    with _LOCK:
        todos, todo = _get_or_raise(todo_id, user_id)

        if title is not None:
            title = title.strip()
            if not title:
                raise ToolError("Title cannot be empty")
            todo.title = title
        if description is not None:
            todo.description = description.strip()
        if status is not None:
            todo.status = status

        todo.updated_at = _now()
        todos[todo_id] = todo
        _save(todos)

    return todo


@mcp.resource("todos://get_all")
def todos_resource() -> list[dict]:
    """List all of your todos as a readable resource"""
    user_id = _current_user("todo:read")

    with _LOCK:
        todos = [t for t in _load().values() if t.owner == user_id]

    todos.sort(key=lambda t: t.created_at, reverse=True)
    return [t.model_dump() for t in todos]


if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=8000)