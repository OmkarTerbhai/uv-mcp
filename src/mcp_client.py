from fastmcp import Client
import asyncio

async def demo() :
    async with Client("http://127.0.0.1:8000/mcp") as client :
        tools = await client.list_tools()
        for tool in tools :
            print(f"{tool.name} => {tool.description}")


async def call_tools() :
    async with Client("http://127.0.0.1:8000/mcp") as client :
        created_todo = await client.call_tool(
            "create_todo",
            {"title": "Make monthly budget",
             "description": "List every expense and savings",
             "status": "Pending"}
        );

        print(f"Created Todo => {created_todo}");

    async with Client("http://127.0.0.1:8000/mcp") as client :
        todos = await client.call_tool(
            "list_todos"
        );

        for todo in todos.data:
            print(f"Todo: {todo}")


    async with Client("http://127.0.0.1:8000/mcp") as client:
        todo = await client.call_tool(
            "get_todo_by_title",  {"todo_title": "monthly"}
        );
        print("_______________________________________________________")

        print(f"Todo found by title: {todo.data}")


async def main():
    await demo()
    await call_tools()

asyncio.run(main())

