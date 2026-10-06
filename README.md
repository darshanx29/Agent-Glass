# Agent Glass
A small, transparent agent harness for local open-weight models (Qwen via Ollama).
Every step is traced to JSONL: exact prompt, raw model output, tool call,
validation result, tool result and stop reason. Runs can be replayed with no model.

## Install
pip install requests flask pytest
ollama pull qwen2.5:3b   (or any Qwen model)

## Run
python run.py            # opens the UI at http://127.0.0.1:5000
python -m agent_glass.loop "What is 23*47?" qwen2.5:7b

## Test
python -m pytest -q      # 15 tests, no model needed
python -m agent_glass.replay traces/<file>.jsonl   # replay without a model

## Files
agent_glass/ (client, tools, loop, trace, replay), viewer/app.py (UI), tests/
