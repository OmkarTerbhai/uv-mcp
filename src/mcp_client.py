import asyncio

from fastmcp import Client
from fastmcp.client.auth import OAuth
from fastmcp.exceptions import ToolError

MCP_URL = "http://localhost:8000/mcp"


def _get_auth_config() -> OAuth:
    return OAuth(
        mcp_url=MCP_URL,
        scopes=["todo:read", "todo:write"],
        client_name="Descope FastMCP Client",
        callback_host="localhost",
    )


async def demo(client: Client) -> None:
    print("=== Tools ===")
    for tool in await client.list_tools():
        print(f"{tool.name} => {tool.description}")

    print("\n=== Resources ===")
    for res in await client.list_resources():
        print(f"{res.name} => {res.description}")

    print("\n=== Who am I ===")
    who = await client.call_tool("whoami")
    print(who.data)


async def call_tools(client: Client) -> None:
    print("\n=== Create ===")
    created = await client.call_tool(
        "create_todo",
        {
            "title": "Make monthly budget",
            "description": "List every expense and savings",
            "status": "Pending",
        },
    )
    todo_id = created.data.id
    print(f"Created Todo => {created.data}")

    print("\n=== List ===")
    todos = await client.call_tool("list_todos")
    for todo in todos.data:
        print(f"Todo: {todo}")

    print("\n=== Get by title ===")
    found = await client.call_tool("get_todo_by_title", {"todo_title": "monthly"})
    print(f"Todo found by title: {found.data}")

    print("\n=== Update ===")
    updated = await client.call_tool(
        "update_todo", {"todo_id": todo_id, "status": "Completed"}
    )
    print(f"Updated Todo => {updated.data}")

    print("\n=== List completed only ===")
    completed = await client.call_tool("list_todos", {"status": "Completed"})
    for todo in completed.data:
        print(f"Todo: {todo}")

    print("\n=== Resource ===")
    contents = await client.read_resource("todos://get_all")
    for item in contents:
        print(item.text)

    print("\n=== Delete ===")
    deleted = await client.call_tool("delete_todo", {"todo_id": todo_id})
    print(deleted.data)


async def main() -> None:
    # One Client = one connection and one OAuth login for the whole run.
    async with Client(MCP_URL, auth=_get_auth_config()) as client:
        try:
            await demo(client)
            await call_tools(client)
        except ToolError as e:
            print(f"\nServer rejected the call: {e}")


if __name__ == "__main__":
    asyncio.run(main())