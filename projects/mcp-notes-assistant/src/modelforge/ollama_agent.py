import asyncio
import json
import math
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SYSTEM_PROMPT = (
    "You are a helpful local assistant. Respond naturally and concisely. "
    "Use MCP tools whenever they help answer the user's request. "
    "For a note title, use read_note_by_title; for a numeric ID, use read_note. "
    "Never show tool-call JSON to the user."
)


def _ollama_timeout() -> float:
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
    except ValueError as error:
        raise RuntimeError("OLLAMA_TIMEOUT must be a positive number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError("OLLAMA_TIMEOUT must be a positive number")
    return timeout


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
    try:
        with urlopen(
            request,
            timeout=_ollama_timeout(),
        ) as response:
            result = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {error.code}: {details}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            "Could not connect to Ollama. Ensure it is running at "
            f"{host}."
        ) from error
    except TimeoutError as error:
        raise RuntimeError("The request to Ollama timed out") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Ollama returned invalid JSON") from error
    except UnicodeDecodeError as error:
        raise RuntimeError("Ollama returned invalid text encoding") from error

    if not isinstance(result, dict):
        raise RuntimeError("Ollama response must be a JSON object")
    return result


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


def _confirm_tool_call(name: str, arguments: dict[str, Any]) -> bool:
    if name != "delete_note":
        return True

    note_id = arguments.get("note_id", "unknown")
    try:
        answer = input(
            f"Ollama requested deletion of note {note_id}. "
            "Type 'yes' to confirm (default: no): "
        )
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().lower() in {"y", "yes"}


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
    working_messages = [dict(message) for message in messages]
    server = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(os.path.dirname(__file__), "main.py")],
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            discovered = await session.list_tools()
            tools = _ollama_tools(discovered.tools)
            if _is_tool_inventory_request(working_messages):
                answer = _format_tool_catalog(discovered.tools)
                working_messages.append({"role": "assistant", "content": answer})
                messages[:] = working_messages
                return answer

            catalog = _tool_catalog(discovered.tools)
            if working_messages and working_messages[0].get("role") == "system":
                system_content = working_messages[0].get("content", "")
                marker = "These are the tools currently available"
                if marker not in system_content:
                    working_messages[0]["content"] = (
                        f"{system_content}\n\n{marker} on this MCP "
                        f"server:\n{catalog}"
                    )

            for _ in range(5):
                response = await asyncio.to_thread(
                    _ollama_chat, working_messages, tools
                )
                message = response.get("message")
                if not isinstance(message, dict):
                    raise RuntimeError("Ollama response did not contain a message")
                working_messages.append(message)
                tool_calls = message.get("tool_calls", [])
                if not isinstance(tool_calls, list):
                    raise RuntimeError("Ollama returned an invalid tool-call list")
                if not tool_calls:
                    fallback_call = _content_tool_call(message.get("content"))
                    if fallback_call is not None:
                        tool_calls = [fallback_call]
                if not tool_calls:
                    answer = message.get("content", "")
                    if not isinstance(answer, str):
                        raise RuntimeError("Ollama response did not contain text")
                    messages[:] = working_messages
                    return answer

                for call in tool_calls:
                    if not isinstance(call, dict) or not isinstance(
                        call.get("function"), dict
                    ):
                        raise RuntimeError("Ollama returned an invalid tool call")
                    function = call["function"]
                    name = function.get("name")
                    if not isinstance(name, str):
                        raise RuntimeError("Ollama tool call did not include a name")
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError as error:
                            raise RuntimeError(
                                "Ollama returned invalid JSON in tool arguments"
                            ) from error
                    if not isinstance(arguments, dict):
                        raise RuntimeError("Ollama returned invalid tool arguments")
                    if not _confirm_tool_call(name, arguments):
                        working_messages.append(
                            {
                                "role": "tool",
                                "content": (
                                    "The user declined this deletion; "
                                    "no note was deleted."
                                ),
                            }
                        )
                        continue
                    result = await session.call_tool(
                        name,
                        arguments=arguments,
                    )
                    working_messages.append(
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
            "Usage: python -m modelforge.ollama_agent [optional question]"
        )
