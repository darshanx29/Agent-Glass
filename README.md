# Agent Glass

**A small, transparent agent harness for local open-weight models.**
When an agent fails, Agent Glass shows you exactly why: was it the prompt, the model, a tool call, a bad argument, or the loop?

Built for the *Best Open-Source AI Project* track, problem statement #5, **See Inside the Agent**.

- Original harness, written from scratch in about 300 lines of Python. No LangChain or other agent framework.
- Runs fully offline on an open-weight model (Qwen2.5) served by [Ollama](https://ollama.com).
- Every step is recorded to a JSONL trace and can be **replayed without a model**.
- Includes a browser UI to run tasks, inspect traces and compare two runs.
- MIT licensed.

---

## The problem

Agent frameworks are black boxes. When something goes wrong, a developer sees a bad final answer and has to guess the cause. This is worse with small local models, which often produce malformed JSON, pick the wrong tool, or loop.

## The idea

Make the harness so small that it can be read in one sitting, and record every decision it makes. From a single trace event you can tell which part failed.

---

## How it works

Each run is a loop (`agent_glass/loop.py`):

1. **Prompt.** The system prompt lists the available tools and tells the model to reply with one JSON object. The harness resends the full message history every step, because the model has no memory between calls.
2. **Model call.** `client.py` sends the messages to Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1/chat/completions`) and returns the raw text.
3. **Parse.** The first JSON object in the reply is extracted. If parsing fails, the error is recorded and fed back to the model.
4. **Validate.** The tool name must exist, and arguments must have the right names and types. Failures are recorded and fed back.
5. **Run the tool.** Tools run inside a try/except, so a crash becomes a recorded `tool_error`.
6. **Feed back.** The result is added to the history and the loop repeats.
7. **Stop** on a final answer, after 8 steps, or when the same call repeats 3 times.

The model only *chooses* a tool by writing JSON. The harness validates and executes it, which is why every action can be traced.

```
task -> prompt + tool list -> Ollama (Qwen) -> raw JSON text
          ^                                        |
          |                               parse -> validate -> run tool
          +------------- result / error fed back -+
                              |
                        one JSONL event per step
```

---

## Features

| Feature | Where |
|---|---|
| Agent loop with step limit and repeated-call detection | `agent_glass/loop.py` |
| Tool registry with schema validation | `agent_glass/tools.py` |
| Structured JSONL tracing of every step | `agent_glass/trace.py` |
| Replay a run from its recording, no model needed | `agent_glass/replay.py` |
| Step-by-step debugger: pause after each model reply and edit it | `--debug` flag on the loop |
| Browser UI: run tasks, inspect traces, replay, compare runs | `viewer/app.py` |
| Fixed task set for measuring the real model | `evaluate.py` |
| One-command launcher | `run.py` |
| Unit tests using a fake model | `tests/` |

### Built-in demo tools

| Tool | Purpose |
|---|---|
| `calculator` | Safe arithmetic (parsed with `ast`, no `eval`) |
| `read_file` | Read a text file, restricted to the `workspace/` folder |
| `fetch_url` | Download a web page, first 2000 characters |
| `get_weather` | Current weather for a city (Open-Meteo, no API key) |

The tools are deliberately simple. The product is the transparent harness around them. Adding a tool takes one decorated function:

```python
@tool("get_time", "Get the current date and time", {"note": "string"})
def get_time(note):
    ...
```

Small models get confused by many tools, so keep the list short.

---

## What the trace records

Each step writes one JSON line to `traces/<run_id>.jsonl`:

| Field | Meaning |
|---|---|
| `messages_sent` | The exact messages the model received (its entire view of the world) |
| `raw_output` | What the model said, before any parsing |
| `parsed_call` | The tool call or final answer extracted from it |
| `validation` | `{ok: true}` or `{ok: false, error: ...}` |
| `tool_args`, `tool_result`, `tool_error`, `duration_ms` | What the tool did |
| `stop_reason` | `final_answer`, `repeated_call`, or `max_steps` |
| `edited_by_user` | Set when the debugger changed the model's output |

### Failure tags in the UI

The UI classifies each failed step so the cause is visible at a glance:

| Tag | Meaning | Example |
|---|---|---|
| `MODEL` | The model produced unusable output or chose a tool that does not exist | Malformed JSON, unknown tool `weather` |
| `ARGUMENTS` | The tool exists but the arguments are invalid | Missing argument, wrong type |
| `TOOL` | The tool itself raised an error | File not found, network failure |
| `LOOP` | The loop had to stop the run | Same call repeated 3 times |

---

## Install

Requirements: Python 3.10+, Git, and [Ollama](https://ollama.com).

```bash
git clone https://github.com/YOUR-USERNAME/agent-glass.git
cd agent-glass
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install requests flask pytest
```

Download a model. Pick one that fits your hardware:

```bash
ollama pull qwen2.5:7b     # most reliable, needs about 5-6 GB of GPU or RAM
ollama pull qwen2.5:3b     # good middle ground, about 2 GB
ollama pull qwen2.5:1.5b   # smallest, fastest, fails more often
```

---

## Run

### One command (UI)

```bash
python run.py
```

This checks that Ollama is running (and starts it if needed), runs the tests, starts the UI and opens http://127.0.0.1:5000.

Options: `--skip-tests` for a faster start, `--demo` to also run and replay a sample task in the terminal.

### From the command line

```bash
python -m agent_glass.loop "What is 23*47?" qwen2.5:7b
python -m agent_glass.loop "What is 23*47?" qwen2.5:7b --debug
python -m agent_glass.replay traces/<trace-file>.jsonl
```

`--debug` pauses after each model reply. Press Enter to continue, or type replacement JSON to change what the model said. Edits are marked `edited_by_user` in the trace.

### The UI

- **Home:** run a task with a model picker and example chips, search past runs, filter failed runs, and tick two runs to compare.
- **Trace page:** one card per step with the raw model output, tool result, failure tag and the exact prompt. Includes **Replay (no model)** and **Compare with**.
- **Compare page:** two runs side by side, a banner showing the first step where they diverge, and per-step latency bars.

The UI is a single file with no CDN links, so it works offline.

---

## Test

```bash
python -m pytest -q
```

The unit tests use a fake model, so they run in under a second and need no Ollama. They cover validation (unknown tool, missing argument, extra argument, wrong type), parsing, the calculator and file sandbox, and the loop's stop conditions (final answer, recovery from an unknown tool, repeated call, step limit).

To measure the real model on a fixed task set:

```bash
python evaluate.py qwen2.5:7b
```

It prints pass/fail, time and stop reason for each task. Open any failure in the UI to see the cause.

### Try a failure on purpose

```bash
python -m agent_glass.loop "Use the tool called weather to get the temperature in Nashik" qwen2.5:7b
```

No tool called `weather` exists (the real one is `get_weather`), so the trace shows a failed validation tagged `MODEL`. Replay it to reproduce the failure exactly, with no model.

---

## Project layout

```
agent-glass/
  agent_glass/
    client.py      # HTTP call to Ollama
    tools.py       # tool registry, validation, demo tools
    loop.py        # the agent loop and --debug mode
    trace.py       # JSONL event writer
    replay.py      # re-run a trace with no model
  viewer/app.py    # Flask UI (single file, offline)
  tests/           # pytest tests with a fake model
  workspace/       # the only folder file tools may touch
  traces/          # generated run traces (git-ignored)
  evaluate.py      # fixed task set for the real model
  run.py           # one-command launcher
  LICENSE          # MIT
```

---

## Design choices

- **No framework.** Frameworks hide the loop. The goal here is to make the loop visible.
- **Open-weight local model.** It works offline with no API key, and small models fail often enough to give the tracing real failures to explain.
- **JSONL traces.** Simple to read, diff and replay.
- **Errors are feedback, not crashes.** A bad parse or invalid call is recorded and sent back to the model. Each retry uses one of the 8 steps.
- **Sandboxed tools.** File tools cannot leave `workspace/`, and the calculator never uses `eval`. There are deliberately no shell or code-execution tools.

---

## Limitations

- The demo tools are simple on purpose. This is a debugging and teaching harness, not a production assistant.
- Small models become unreliable with many tools. Around 5 to 8 is a sensible limit for a 7B model.
- A successful run can still give a useless answer, for example when a tool returns an error page. The trace shows this, but the UI does not yet flag it automatically.
- Hardware matters. On a GPU with limited memory, `qwen2.5:7b` can fail to load (`cudaMalloc failed: out of memory`). Use a smaller model, or run on CPU by starting Ollama with `CUDA_VISIBLE_DEVICES=-1`.
- Replay reproduces recorded model outputs and tool results. It does not re-run the tools.
- The UI runs one task at a time.

## Roadmap

- Automatic flag for runs that "succeed" with an unhelpful answer
- Per-task tool subsets to help very small models
- Pass-rate comparison across model sizes (1.5B, 3B, 7B) on a fixed scenario set
- Step debugger inside the UI

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `500 Internal Server Error` from Ollama | Usually out of memory. Try a smaller model, close other apps, or run on CPU |
| `Connection refused` | Start the Ollama app |
| `No module named 'agent_glass'` | Run commands from the project root folder |
| `Model not found` | The name must match `ollama list` exactly |
| UI says "Ollama not detected" | Start Ollama and refresh the page |

---

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgements

Language model: [Qwen2.5](https://github.com/QwenLM/Qwen2.5) (open weights, by Alibaba Cloud), served locally by [Ollama](https://ollama.com). The harness, tracing, replay and UI are original work.
