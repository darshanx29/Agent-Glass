import json, pathlib, sys, requests
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from flask import Flask, render_template_string, request, redirect, url_for, abort
from agent_glass import loop
from agent_glass.replay import replay

app = Flask(__name__)
TRACES = pathlib.Path("traces")

def models():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3).json()
        return [m["name"] for m in r["models"]]
    except Exception:
        return []

def load(name):
    path = TRACES / pathlib.Path(name).name
    if not path.exists():
        abort(404)
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

def failed(e):
    v = e.get("validation") or {}
    return e.get("event") == "step" and (v.get("ok") is False or bool(e.get("tool_error")))

def summarize(events):
    start = next((e for e in events if e.get("event") == "run_start"), {})
    steps = [e for e in events if e.get("event") == "step"]
    stop = next((e["stop_reason"] for e in reversed(events) if e.get("stop_reason")), "unknown")
    return {"task": start.get("task", "?"), "model": start.get("model", "?"),
            "steps": len(steps), "failed": sum(failed(s) for s in steps), "stop": stop}

CSS = """<style>
*{box-sizing:border-box} body{font-family:system-ui,sans-serif;margin:0;background:#f1f5f9;color:#0f172a}
header{background:#0f172a;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:12px}
header a{color:#fff;text-decoration:none;font-weight:700;font-size:20px} header small{color:#94a3b8}
main{max-width:960px;margin:24px auto;padding:0 16px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 18px;margin:12px 0}
.bad{border-left:6px solid #dc2626;background:#fef2f2} .ok{border-left:6px solid #16a34a}
input[type=text],select{padding:10px;border:1px solid #cbd5e1;border-radius:8px;font-size:15px}
input[type=text]{width:100%;margin-bottom:8px}
button{background:#2563eb;color:#fff;border:0;padding:10px 18px;border-radius:8px;font-size:15px;cursor:pointer}
button:disabled{background:#94a3b8} .ghost{background:#475569}
pre{background:#0f172a;color:#e2e8f0;padding:10px;border-radius:8px;white-space:pre-wrap;word-break:break-word;margin:4px 0}
.tag{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;background:#e2e8f0;margin-right:4px}
.red{background:#fee2e2;color:#991b1b} .green{background:#dcfce7;color:#166534}
h4{margin:12px 0 2px;font-size:13px;color:#475569;text-transform:uppercase;letter-spacing:.04em}
summary{cursor:pointer;font-weight:600;margin-top:10px} a{color:#2563eb}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
</style>"""

HEAD = CSS + """<header><a href="/">Agent Glass</a><small>see exactly what your agent did and why</small></header><main>"""

INDEX = HEAD + """
<div class="card">
  <h3 style="margin-top:0">Run the agent</h3>
  <form method="post" action="/run" onsubmit="b=this.querySelector('button');b.disabled=true;b.textContent='Running... (can take a minute)'">
    <input type="text" name="task" placeholder="e.g. What is 23*47?   or   How many lines are in notes.txt?" required>
    <div class="row">
      <select name="model">
        {% for m in models %}<option>{{ m }}</option>{% else %}<option>qwen2.5:7b</option>{% endfor %}
      </select>
      <button>Run</button>
      {% if not models %}<span class="tag red">Ollama not detected: start the Ollama app</span>{% endif %}
    </div>
  </form>
</div>
<h3>Past runs</h3>
{% for name, s in runs %}
<div class="card {{ 'bad' if s.failed or s.stop != 'final_answer' else 'ok' }}">
  <a href="/trace/{{ name }}"><b>{{ s.task }}</b></a><br>
  <span class="tag">{{ s.model }}</span><span class="tag">{{ s.steps }} steps</span>
  <span class="tag {{ 'red' if s.failed else 'green' }}">{{ s.failed }} failed</span>
  <span class="tag {{ 'green' if s.stop == 'final_answer' else 'red' }}">{{ s.stop }}</span>
</div>
{% else %}<p>No runs yet. Type a task above.</p>{% endfor %}
</main>"""

TRACE = HEAD + """
<a href="/">&larr; all runs</a>
<div class="card {{ 'bad' if s.failed or s.stop != 'final_answer' else 'ok' }}">
  <h2 style="margin-top:0">{{ s.task }}</h2>
  <span class="tag">{{ s.model }}</span><span class="tag">{{ s.steps }} steps</span>
  <span class="tag {{ 'red' if s.failed else 'green' }}">{{ s.failed }} failed</span>
  <span class="tag {{ 'green' if s.stop == 'final_answer' else 'red' }}">stop: {{ s.stop }}</span>
  {% if answer %}<h4>Final answer</h4><pre>{{ answer }}</pre>{% endif %}
  <form method="post" action="/replay/{{ name }}" style="margin-top:10px">
    <button class="ghost">Replay this run (no model)</button>
  </form>
</div>
{% for e in steps %}
<div class="card {{ 'bad' if failed(e) else 'ok' }}">
  <b>Step {{ e.step }}</b>
  {% if failed(e) %}<span class="tag red">FAILED</span>{% endif %}
  {% if e.edited_by_user %}<span class="tag">edited by user</span>{% endif %}
  {% if e.validation %}<span class="tag {{ 'green' if e.validation.ok else 'red' }}">validation: {{ 'ok' if e.validation.ok else e.validation.error }}</span>{% endif %}
  {% if e.stop_reason %}<span class="tag">{{ e.stop_reason }}</span>{% endif %}
  <h4>1. What the model said (raw)</h4><pre>{{ e.raw_output }}</pre>
  <h4>2. Parsed tool call</h4><pre>{{ e.parsed_call | tojson(indent=2) }}</pre>
  {% if e.tool_args is defined %}
  <h4>3. Tool result ({{ e.duration_ms }} ms)</h4>
  <pre>args:   {{ e.tool_args | tojson }}
result: {{ e.tool_result }}
error:  {{ e.tool_error }}</pre>
  {% endif %}
  <details><summary>Exact prompt the model saw ({{ e.messages_sent|length }} messages)</summary>
  {% for m in e.messages_sent %}<h4>{{ m.role }}</h4><pre>{{ m.content }}</pre>{% endfor %}
  </details>
</div>
{% endfor %}
</main>"""

@app.route("/")
def index():
    runs = []
    if TRACES.exists():
        for p in sorted(TRACES.glob("*.jsonl"), reverse=True):
            runs.append((p.name, summarize(load(p.name))))
    return render_template_string(INDEX, runs=runs, models=models())

@app.route("/run", methods=["POST"])
def run():
    answer, path = loop.run(request.form["task"], request.form["model"])
    return redirect(url_for("trace", name=pathlib.Path(path).name))

@app.route("/replay/<name>", methods=["POST"])
def do_replay(name):
    answer, path = replay(str(TRACES / pathlib.Path(name).name))
    return redirect(url_for("trace", name=pathlib.Path(path).name))

@app.route("/trace/<name>")
def trace(name):
    events = load(name)
    steps = [e for e in events if e.get("event") == "step"]
    answer = next((e["parsed_call"]["final"] for e in reversed(steps)
                   if isinstance(e.get("parsed_call"), dict) and "final" in e["parsed_call"]), None)
    return render_template_string(TRACE, s=summarize(events), steps=steps,
                                  failed=failed, name=name, answer=answer)

if __name__ == "__main__":
    app.run(debug=False, threaded=False)