import json, sys, time
from .client import chat
from .tools import TOOLS, describe_tools, validate_args
from .trace import Trace

SYSTEM = """You are an agent that can use tools.
Available tools:
{tools}

Reply with ONLY one JSON object, nothing else.
To use a tool: {{"tool": "<name>", "args": {{...}}}}
To finish: {{"final": "<your answer>"}}"""

def parse(raw):
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(raw[start:end + 1])

def run(task, model="qwen2.5:3b", max_steps=8, repeat_limit=3):
    trace = Trace(task, model)
    messages = [
        {"role": "system", "content": SYSTEM.format(tools=describe_tools())},
        {"role": "user", "content": task},
    ]
    seen = []
    for step in range(1, max_steps + 1):
        event = {"event": "step", "step": step, "messages_sent": list(messages)}
        raw = chat(messages, model)
        event["raw_output"] = raw

        def feedback(problem):
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Error: {problem}. Reply with one valid JSON object."})

        try:
            call = parse(raw)
        except Exception as e:
            event.update(parsed_call=None, validation={"ok": False, "error": f"parse: {e}"})
            trace.emit(event); feedback(f"parse failed ({e})"); continue
        event["parsed_call"] = call

        if "final" in call:
            event.update(validation={"ok": True}, stop_reason="final_answer")
            trace.emit(event)
            return call["final"], trace.path

        name, args = call.get("tool"), call.get("args", {})
        err = validate_args(name, args)
        if err:
            event["validation"] = {"ok": False, "error": err}
            trace.emit(event); feedback(err); continue
        event["validation"] = {"ok": True}

        key = json.dumps([name, args], sort_keys=True)
        seen.append(key)
        if seen.count(key) >= repeat_limit:
            event["stop_reason"] = "repeated_call"
            trace.emit(event)
            return None, trace.path

        t0 = time.time()
        try:
            result, error = TOOLS[name]["fn"](**args), None
        except Exception as e:
            result, error = None, f"{type(e).__name__}: {e}"
        event.update(tool_args=args, tool_result=result, tool_error=error,
                     duration_ms=round((time.time() - t0) * 1000))
        trace.emit(event)
        messages.append({"role": "assistant", "content": raw})
        observation = f"Tool error: {error}" if error else f"Tool result: {result}"
        messages.append({"role": "user", "content": observation})

    trace.emit({"event": "run_end", "stop_reason": "max_steps"})
    return None, trace.path

if __name__ == "__main__":
    task = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:3b"
    answer, path = run(task, model)
    print("Answer:", answer)
    print("Trace:", path)