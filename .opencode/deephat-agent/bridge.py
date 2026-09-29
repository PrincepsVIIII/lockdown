"""Local DeepHat -> OpenCode adapter. It translates requests; it executes no tools."""

import argparse
import copy
import json
import ntpath
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, ValidationError

MODEL = "deephat"
CONTEXT = 32768
MAX_OUTPUT = 4096
FORMAT = """You can use the tools listed below to complete the user's task.
To request a tool, output ONLY a JSON array containing ONE object with name and arguments.
Example: [{"name":"read","arguments":{"filePath":"example.txt"}}]
Use exactly the tool names and argument names provided. Never invent tools.
Request only the next operation. Never combine dependent operations in one response.
Stop after requesting a tool and wait for its result. Use tool results to decide
the next step. Read an existing file before editing it.
Do not repeat a successful operation. Once the task is complete, reply briefly in
plain text. If the user asks for an explanation or example, answer in plain text.
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def plain_content(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(p.get("type") == "text" for p in content):
        return "\n".join(p["text"] for p in content)
    raise ValueError("This DeepHat adapter supports text messages only")


def project_directory(messages):
    for message in messages:
        if message.get("role") in ("system", "developer"):
            match = re.search(r"(?m)^\s*Working directory:[ \t]*([^\r\n]+)", plain_content(message.get("content")))
            if match and ntpath.isabs(match.group(1).strip()):
                return match.group(1).strip()
    return None


def expand_file_paths(calls, directory):
    if not directory or not calls:
        return calls
    for call in calls:
        if call["function"]["name"] not in ("read", "write", "edit"):
            continue
        args = json.loads(call["function"]["arguments"])
        path = args.get("filePath")
        if isinstance(path, str) and not ntpath.isabs(path):
            if ntpath.splitdrive(path)[0]:
                raise ValueError("Drive-relative file paths are not supported")
            args["filePath"] = ntpath.normpath(ntpath.join(directory, path)).replace("\\", "/")
            call["function"]["arguments"] = encode(args)
    return calls


def prompt_for(messages, tools):
    # DeepHat's published ChatML format uses a tool role and JSON-array history:
    # https://huggingface.co/DeepHat/DeepHat-V1-7B/blob/main/chat_template.jinja
    system = [plain_content(m.get("content")) for m in messages
              if m["role"] in ("system", "developer")]
    if tools:
        functions = copy.deepcopy([t["function"] for t in tools])
        path_instruction = "Use absolute file paths."
        if project_directory(messages):
            path_instruction = "For read, write, and edit, use a short project-relative filePath, such as greeting.py. The adapter resolves it against the working directory."
            for function in functions:
                if function["name"] in ("read", "write", "edit"):
                    properties = function.get("parameters", {}).get("properties", {})
                    if "filePath" in properties:
                        properties["filePath"]["description"] = "Project-relative file path. Use a filename or relative path inside the working directory."
        system.append(FORMAT + path_instruction + "\n<tools>" + encode(functions) + "</tools>")
    chunks = ["<|im_start|>system\n" + "\n".join(system) + "<|im_end|>\n"]
    for message in messages:
        role = message["role"]
        if role in ("system", "developer"):
            continue
        if role not in ("user", "assistant", "tool"):
            raise ValueError("Unsupported message role")
        content = plain_content(message.get("content"))
        if role == "assistant" and message.get("tool_calls"):
            calls = []
            for call in message["tool_calls"]:
                function = call["function"]
                args = function["arguments"]
                calls.append({"name": function["name"],
                              "arguments": json.loads(args) if isinstance(args, str) else args})
            content = encode(calls)
        chunks.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    return "".join(chunks) + "<|im_start|>assistant\n"


def calls_from(text, tools):
    """Accept only whole-response calls, and validate against advertised tools."""
    if not tools:
        return None
    payload = text.strip()
    tagged = re.fullmatch(r"<tool_call>\s*(.*?)\s*</tool_call>", payload, re.S)
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", payload, re.S)
    if tagged or fenced:
        payload = (tagged or fenced).group(1).strip()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        if tagged:
            raise ValueError("Malformed tool-call JSON")
        return None
    if isinstance(value, dict):
        value = [value]
    if value == []:
        return []
    if not isinstance(value, list) or not value or not all(
        isinstance(item, dict) and "name" in item and "arguments" in item for item in value
    ):
        return None
    definitions = {t["function"]["name"]: t["function"] for t in tools}
    calls = []
    for item in value:
        if set(item) != {"name", "arguments"} or not isinstance(item["name"], str):
            raise ValueError("Invalid tool-call envelope")
        definition = definitions.get(item["name"])
        if definition is None:
            raise ValueError("Model requested a tool that is not available")
        args = item["arguments"]
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")
        schema = definition.get("parameters", {"type": "object"})
        if set(args) - set(schema.get("properties", {})):
            raise ValueError("Model supplied unknown tool arguments")
        try:
            Draft202012Validator(schema).validate(args)
        except ValidationError as error:
            raise ValueError("Tool arguments do not match the declared schema: " + error.message) from error
        calls.append({"id": "call_" + uuid.uuid4().hex, "type": "function",
                      "function": {"name": item["name"], "arguments": encode(args)}})
    return calls


def completion(body):
    if not isinstance(body, dict):
        raise ValueError("Request must be a JSON object")
    if body.get("model") != MODEL:
        raise ValueError("This adapter serves only the deephat model")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a nonempty array")
    tools = body.get("tools") or []
    if body.get("tool_choice") == "none":
        tools = []
    elif body.get("tool_choice") not in (None, "auto"):
        raise ValueError("Only auto and none tool_choice are supported")
    if body.get("n", 1) != 1:
        raise ValueError("Only one completion is supported")
    maximum = min(int(body.get("max_tokens") or body.get("max_completion_tokens") or MAX_OUTPUT), MAX_OUTPUT)
    if maximum < 1:
        raise ValueError("max_tokens must be positive")
    request = {"model": MODEL, "raw": True, "stream": False,
               "prompt": prompt_for(messages, tools), "keep_alive": "5m",
               "options": {"temperature": 0, "num_ctx": CONTEXT, "num_predict": maximum,
                           "stop": ["<|im_end|>", "<|im_start|>"]}}
    upstream = Request("http://127.0.0.1:11434/api/generate", data=encode(request).encode(),
                       headers={"Content-Type": "application/json"})
    with urlopen(upstream, timeout=240) as response:
        result = json.load(response)
    if result.get("error"):
        raise RuntimeError("Ollama: " + str(result["error"]))
    if result.get("done_reason") == "length":
        raise RuntimeError("DeepHat reached the output limit; no incomplete tool call was dispatched")
    content = result.get("response", "").strip()
    calls = calls_from(content, tools)
    # OpenCode runs a batch concurrently. DeepHat often batches dependent edits;
    # expose only the first validated call and let it replan from that result.
    if calls:
        calls = calls[:1]
        calls = expand_file_paths(calls, project_directory(messages))
    message = {"role": "assistant", "content": None if calls else ("" if calls == [] else content)}
    if calls:
        message["tool_calls"] = calls
    usage = {"prompt_tokens": result.get("prompt_eval_count", 0),
             "completion_tokens": result.get("eval_count", 0)}
    usage["total_tokens"] = sum(usage.values())
    return {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion",
            "created": int(time.time()), "model": MODEL,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "tool_calls" if calls else "stop"}], "usage": usage}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Do not save prompts, file contents, or tool arguments in logs.

    def send_json(self, status, value):
        data = encode(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"service": "deephat-agent", "version": 1})
        elif self.path == "/v1/models":
            self.send_json(200, {"object": "list", "data": [
                {"id": MODEL, "object": "model", "created": 0, "owned_by": "local"}]})
        else:
            self.send_json(404, {"error": {"message": "Not found"}})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_json(404, {"error": {"message": "Not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4 * 1024 * 1024:
                raise ValueError("Invalid request size")
            # Browser requests are not clients of this local development endpoint.
            if self.headers.get("Origin"):
                self.send_json(403, {"error": {"message": "Browser origins are not allowed"}})
                return
            body = json.loads(self.rfile.read(length))
            result = completion(body)
            if not body.get("stream"):
                self.send_json(200, result)
                return
            # Buffer generation to validate complete calls before emitting any action.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            message = dict(result["choices"][0]["message"])
            if message.get("tool_calls"):
                message["tool_calls"] = [dict(call, index=i) for i, call in enumerate(message["tool_calls"])]
            base = {key: result[key] for key in ("id", "created", "model")}
            base["object"] = "chat.completion.chunk"
            chunks = [dict(base, choices=[{"index": 0, "delta": message, "finish_reason": None}]),
                      dict(base, choices=[{"index": 0, "delta": {},
                                          "finish_reason": result["choices"][0]["finish_reason"]}],
                           usage=result["usage"])]
            for chunk in chunks:
                self.wfile.write(("data: " + encode(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, KeyError, TypeError) as error:
            self.send_json(400, {"error": {"message": str(error), "type": "invalid_request_error"}})
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            self.send_json(502, {"error": {"message": str(error), "type": "upstream_error"}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"DeepHat adapter listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
