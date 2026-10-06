import json, sys
from . import loop, tools

def replay(trace_path):
    events = [json.loads(l) for l in open(trace_path, encoding="utf-8") if l.strip()]
    start = next(e for e in events if e["event"] == "run_start")
    steps = [e for e in events if e["event"] == "step"]
    outputs = iter(s["raw_output"] for s in steps)
    tool_steps = iter(s for s in steps if "tool_args" in s)

    real_chat = loop.chat
    real_fns = {n: t["fn"] for n, t in tools.TOOLS.items()}

    def fake_tool(**kwargs):
        rec = next(tool_steps)
        if rec["tool_error"]:
            raise RuntimeError(rec["tool_error"])
        return rec["tool_result"]

    loop.chat = lambda messages, model: next(outputs)
    for t in tools.TOOLS.values():
        t["fn"] = fake_tool
    try:
        return loop.run(start["task"], start["model"])
    finally:
        loop.chat = real_chat
        for n, fn in real_fns.items():
            tools.TOOLS[n]["fn"] = fn

if __name__ == "__main__":
    answer, path = replay(sys.argv[1])
    print("Replayed answer:", answer)
    print("New trace:", path)