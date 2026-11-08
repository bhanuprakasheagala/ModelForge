import asyncio
import json
import os
import re
import sys
from typing import Any
from urllib.request import Request, urlopen

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SYSTEM_PROMPT = (
    "You are a helpful local assistant. Respond naturally and concisely. "
    "Use MCP tools whenever they help answer the user's request. "
    "For a note title, use read_note_by_title; for a numeric ID, use read_note. "
    "Never show tool-call JSON to the user."
)


def _ollama_chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = json.dumps(
        {
            "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(
        request,
        timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
    ) as response:
        return json.load(response)


def _ollama_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


def _tool_catalog(mcp_tools: list[Any]) -> str:
    return "\n".join(
        f"- {tool.name}: {tool.description or 'No description provided.'}"
        for tool in mcp_tools
    )


def _is_tool_inventory_request(messages: list[dict[str, Any]]) -> bool:
    user_messages = [
        message["content"].lower()
        for message in messages
        if message.get("role") == "user"
        and isinstance(message.get("content"), str)
    ]
    if not user_messages:
        return False
    request = user_messages[-1]
    return bool(
        re.search(r"\b(list|show|what are|which)\b", request)
        and re.search(r"\b(tools?|functions?)\b", request)
    )


def _format_tool_catalog(mcp_tools: list[Any]) -> str:
    lines = [f"This MCP server provides {len(mcp_tools)} tools:"]
    lines.extend(
        f"{index}. {tool.name} — {tool.description or 'No description provided.'}"
        for index, tool in enumerate(mcp_tools, start=1)
    )
    return "\n".join(lines)


def _tool_result_text(result: Any) -> str:
    parts = []
    for content in result.content:
        text = getattr(content, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(content.model_dump_json())
    return "\n".join(parts)


def _content_tool_call(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str):
        return None
    try:
        candidate = json.loads(content.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(candidate, dict):
        return None
    name = candidate.get("name")
    arguments = candidate.get("parameters", candidate.get("arguments", {}))
    if isinstance(name, str) and isinstance(arguments, dict):
        return {"function": {"name": name, "arguments": arguments}}
    return None


async def ask_with_mcp_tools(prompt: str) -> str:
    return await _chat_with_mcp_tools(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    )


async def _chat_with_mcp_tools(messages: list[dict[str, Any]]) -> str:
    server = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(os.path.dirname(__file__), "main.py")],
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            discovered = await session.list_tools()
            tools = _ollama_tools(discovered.tools)
            if _is_tool_inventory_request(messages):
                return _format_tool_catalog(discovered.tools)

            catalog = _tool_catalog(discovered.tools)
            if messages and messages[0].get("role") == "system":
                system_content = messages[0].get("content", "")
                marker = "These are the tools currently available"
                if marker not in system_content:
                    messages[0]["content"] = (
                        f"{system_content}\n\n{marker} on this MCP "
                        f"server:\n{catalog}"
                    )

            for _ in range(5):
                response = await asyncio.to_thread(_ollama_chat, messages, tools)
                message = response.get("message", {})
                messages.append(message)
                tool_calls = message.get("tool_calls", [])
                if not tool_calls:
                    fallback_call = _content_tool_call(message.get("content"))
                    if fallback_call is not None:
                        tool_calls = [fallback_call]
                if not tool_calls:
                    return message.get("content", "")

                for call in tool_calls:
                    function = call["function"]
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    result = await session.call_tool(
                        function["name"],
                        arguments=arguments,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "content": _tool_result_text(result),
                        }
                    )

            raise RuntimeError("Ollama exceeded the maximum tool-call rounds")


async def interactive_chat() -> None:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]
    print("Ollama MCP chat (type 'exit' or 'quit' to leave)")
    while True:
        try:
            prompt = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return
        if prompt.lower() in {"exit", "quit"}:
            print("Goodbye!")
            return
        if not prompt:
            continue

        messages.append({"role": "user", "content": prompt})
        try:
            answer = await _chat_with_mcp_tools(messages)
        except RuntimeError as error:
            messages.pop()
            print(f"Error: {error}")
            continue
        print(f"Assistant: {answer}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        asyncio.run(interactive_chat())
    elif len(sys.argv) == 2 and sys.argv[1].strip():
        print(asyncio.run(ask_with_mcp_tools(sys.argv[1])))
    else:
        raise SystemExit(
            "Usage: python src/ollama_agent.py [optional question]"
        )
