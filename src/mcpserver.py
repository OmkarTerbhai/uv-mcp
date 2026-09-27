import json

from fastmcp import FastMCP;
from typing import Literal, Annotated;
from pathlib import Path;
import threading;
from uuid import uuid4;
from datetime import datetime, timezone;
from pydantic import BaseModel
from fastmcp.exceptions import ToolError;

mcp: FastMCP = FastMCP(name = "Todo",
                       instructions="A simple todo list app,"
                                    "provides tools like"
                                    "create_todo, list_todos, get_todo_id, update_todo, get_todo_title and delete_todo");

status_enum = Literal["Pending", "Completed", "Deleted"];

STORE_PATH = Path(__file__).with_name("todos.json");

_LOCK = threading.Lock();

class Todo(BaseModel) :
    id: str
    title: str
    description : str = ""
    status: status_enum = "pending"
    created_at: str
    updated_at: str

def _now() -> str :
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat();

def _load() -> dict[str, Todo] :
    if not STORE_PATH.exists() :
        return {};

    raw_data = json.loads(STORE_PATH.read_text() or []);
    return {item.get("id") : Todo.model_validate(item)
             for item in raw_data};


def _save(todos: dict[str, Todo]) -> None :
    (STORE_PATH
        .write_text(
        json.dumps([todo.model_dump() for todo in todos.values()], indent=2) + "\n"
    ));

def _get_or_raise(tool_id : str) -> tuple[dict[str, Todo], Todo] :
    todos = _load();

    filtered_todo: Todo = todos.get(tool_id);

    if filtered_todo is None :
        raise ValueError(f"Todo with id {tool_id} is not present")

    return todos, filtered_todo;

@mcp.tool
def create_todo(
        title: Annotated[str, "Short title of the todo"],
        description : Annotated[str, "Optional long description"] = "",
        status : Annotated[status_enum, "pending, completed or deleted"] = "pending"
) -> Todo | None :

    """Creates a new todo and returns it"""

    title = title.strip();

    if not title :
        raise ToolError("Title cannot be empty");

    now = _now();
    todo = Todo(
        id = uuid4().hex[:8],
        title=title,
        description=description.strip(),
        status=status,
        created_at=now,
        updated_at=now
    );

    with _LOCK :
        todos = _load();
        todos[todo.id] = todo;
        _save(todos);

    return todo;

@mcp.tool
def list_todos(
        status: Annotated[status_enum | None, "pending, completed, deleted or None to list all"] = None
) -> list[Todo] :
    """Lists todos in reverse chronological order. Optionally
    filter by status"""

    with _LOCK :
        todos = list(_load().values());

        if status is not None :
            todos = [todo for todo in todos if todo.status == status];

        todos.sort(key=lambda t : t.created_at, reverse=True);

        return todos;

@mcp.tool
def get_todo(
        todo_id : Annotated[str, "The ID of the todo to get"]
) -> Todo | None :

    """Get a todo by ID"""

    with _LOCK :
        _,todo = _get_or_raise(todo_id);

    return todo;

@mcp.tool
def get_todo_by_title(
        todo_title: Annotated[str, "Title of todo to be partiall matched"]
) -> Todo | None :

    """Get the todo whose title partially matches with given title"""

    todo_title = todo_title.strip();

    if not todo_title :
        raise ValueError("Title cannot be null");

    todos = _load().values();

    for t in todos :
        if todo_title in t.title :
            return t;

    return None;


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)




