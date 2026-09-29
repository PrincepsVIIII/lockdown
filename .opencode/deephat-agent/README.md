# DeepHat agent adapter

Uses the existing local `deephat` Ollama model with DeepHat's ChatML tool-result
roles and JSON-array tool history. Converts complete validated tool requests into
the OpenAI-compatible tool calls OpenCode expects. It never executes tools itself.

Start from the directory you want to work in:

```powershell
opencode-deephat
```

Or run the launcher directly:

```powershell
& "$env:USERPROFILE\.config\opencode\deephat-agent\start.ps1"
```

The launcher starts a hidden adapter on `127.0.0.1:11435`, opens OpenCode with the
`deephat` agent, and stops its adapter when OpenCode exits. Ollama must already be
running on `127.0.0.1:11434`. The existing Qwen default remains available through
the normal `opencode` command. No service or startup task is installed.

Python 3.13 and `jsonschema` are used from the existing local Python installation.
`requirements.txt` records the dependency for reinstalling elsewhere.

## Behavior and limits

- Text only, 32,768-token context, up to 4,096 output tokens.
- Only complete responses consisting of recognized tool-call JSON (optionally
  fenced or wrapped in `<tool_call>`) are translated. Prose is left as prose.
- Tool names and arguments must match tools enabled in the request; unknown
  names, extra arguments, schema violations, and truncated output are rejected.
- One tool call is dispatched per model turn, so dependent file operations do
  not race each other. DeepHat decides the next step after seeing the result.
- Responses are buffered until validation completes, so text appears in chunks.
- OpenCode retains its normal permission enforcement.
- Relative paths for read/write/edit are expanded using the working directory
  supplied in OpenCode's system context, avoiding long-path copying errors.
- A compatible parser enables tool execution; it does not guarantee that a 7B
  model will plan complex work correctly or finish every task.

Run parser tests with `python -m unittest discover -s . -p test_bridge.py -v`.

Template reference: https://huggingface.co/DeepHat/DeepHat-V1-7B/blob/main/chat_template.jinja
