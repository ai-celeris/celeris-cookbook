#!/usr/bin/env python3
"""Compile and execute the code snippets published in the cookbook."""

import contextlib
import io
import json
import os
import re
import shlex
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(
    r"^```(?P<language>[^\s`]*)?(?P<meta>[^\n]*)\n(?P<code>.*?)^```$",
    re.MULTILINE | re.DOTALL,
)
SUPPORTED_FENCES = {"json", "python", "sh", "text", "ts"}


def registered_sources() -> list[Path]:
    registry = yaml.safe_load((ROOT / "registry.yaml").read_text()) or []
    return [ROOT / entry["path"] for entry in registry]


def metadata(raw: str) -> dict[str, str]:
    return dict(token.split("=", 1) for token in shlex.split(raw) if "=" in token)


def markdown_blocks(text: str) -> list[tuple[str, dict[str, str], str]]:
    return [
        (match.group("language"), metadata(match.group("meta")), match.group("code"))
        for match in FENCE.finditer(text)
    ]


def notebook_cells(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return ["".join(cell.get("source", [])) for cell in notebook["cells"] if cell["cell_type"] == "code"]


def check_e2e_metadata(source: Path, index: int, values: dict[str, str]) -> None:
    classification = values.get("docs-e2e") or values.get("classification")
    if classification not in {"live", "skip"}:
        raise ValueError(f"{source.relative_to(ROOT)}: snippet {index} needs docs-e2e=live|skip")
    if classification == "live" and not (values.get("expect") or values.get("expectation")):
        raise ValueError(f"{source.relative_to(ROOT)}: live snippet {index} needs expect=...")


def check_static_syntax(sources: list[Path]) -> tuple[int, int]:
    fenced = 0
    cells = 0
    for source in sources:
        if source.suffix == ".ipynb":
            notebook = json.loads(source.read_text())
            check_e2e_metadata(source, 1, notebook.get("metadata", {}).get("docs_e2e", {}))
            for cell_index, cell in enumerate(notebook["cells"], 1):
                if cell["cell_type"] != "markdown":
                    continue
                for fence_index, (_language, values, _code) in enumerate(
                    markdown_blocks("".join(cell.get("source", []))), 1
                ):
                    check_e2e_metadata(source, cell_index * 1000 + fence_index, values)
                    fenced += 1
            for index, code in enumerate(notebook_cells(source), 1):
                compile(code, f"{source.relative_to(ROOT)}:cell-{index}", "exec")
                cells += 1
            continue

        for index, (language, values, code) in enumerate(markdown_blocks(source.read_text()), 1):
            check_e2e_metadata(source, index, values)
            if language not in SUPPORTED_FENCES:
                raise ValueError(f"{source.relative_to(ROOT)}: fence {index} has unsupported language {language!r}")
            if language == "python":
                compile(code, f"{source.relative_to(ROOT)}:fence-{index}", "exec")
            elif language == "json":
                json.loads(code)
            elif language == "sh":
                result = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True, check=False)
                if result.returncode:
                    raise SyntaxError(f"{source.relative_to(ROOT)}:fence-{index}: {result.stderr.strip()}")
            fenced += 1
    return fenced, cells


class FakeOpenAIHandler(BaseHTTPRequestHandler):
    requests: list[tuple[str, dict]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length))
        self.requests.append((self.path, body))
        prompt = json.dumps(body.get("messages", []))
        if "Largest city in Australia" in prompt:
            content = json.dumps({"name": "Sydney", "country": "Australia"})
        elif "List three uses" in prompt:
            content = "Classification.\nExtraction.\nRouting."
        elif "context window" in prompt:
            content = "A context window is the text a model can process at once. Input and output share that space."
        else:
            content = "Hello from the snippet test."

        if body.get("stream"):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            midpoint = len(content) // 2
            for part in (content[:midpoint], content[midpoint:]):
                chunk = {
                    "id": "chatcmpl-snippet",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": body.get("model"),
                    "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return

        payload = json.dumps(
            {
                "id": "chatcmpl-snippet",
                "object": "chat.completion",
                "created": 0,
                "model": body.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args) -> None:
        return


def execute_python_snippets() -> int:
    FakeOpenAIHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    old_base_url = os.environ.get("CELERIS_BASE_URL")
    old_api_key = os.environ.get("CELERIS_API_KEY")
    os.environ["CELERIS_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
    os.environ["CELERIS_API_KEY"] = "snippet-test-key"

    executed = 0
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            notebook = ROOT / "examples/getting-started/getting-started.ipynb"
            namespace = {"__name__": "__main__"}
            for index, code in enumerate(notebook_cells(notebook), 1):
                exec(compile(code, f"{notebook.relative_to(ROOT)}:cell-{index}", "exec"), namespace)
                executed += 1

            for guide in sorted((ROOT / "guides").glob("*.md")):
                for index, (language, _values, code) in enumerate(markdown_blocks(guide.read_text()), 1):
                    if language != "python":
                        continue
                    namespace = {"__name__": "__main__"}
                    exec(compile(code, f"{guide.relative_to(ROOT)}:fence-{index}", "exec"), namespace)
                    executed += 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        if old_base_url is None:
            os.environ.pop("CELERIS_BASE_URL", None)
        else:
            os.environ["CELERIS_BASE_URL"] = old_base_url
        if old_api_key is None:
            os.environ.pop("CELERIS_API_KEY", None)
        else:
            os.environ["CELERIS_API_KEY"] = old_api_key

    if not FakeOpenAIHandler.requests:
        raise AssertionError("the executable snippets made no API requests")
    for path, body in FakeOpenAIHandler.requests:
        if path != "/v1/chat/completions":
            raise AssertionError(f"unexpected request path: {path}")
        if body.get("model") != "celeris-1":
            raise AssertionError(f"unexpected model: {body.get('model')}")
        max_tokens = body.get("max_tokens")
        if max_tokens not in {256, 512, 2048}:
            raise AssertionError(f"unexpected cookbook max_tokens: {max_tokens}")
        for unsupported in ("response_format", "tools"):
            if unsupported in body:
                raise AssertionError(f"snippet sent unsupported field: {unsupported}")
    return executed


def main() -> int:
    sources = registered_sources()
    fenced, cells = check_static_syntax(sources)
    executed = execute_python_snippets()
    print(f"snippet checks OK ({fenced} fences, {cells} notebook cells, {executed} Python snippets executed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
