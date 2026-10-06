"""Agent Glass UI - single file, fully offline (no CDN). Run: python viewer/app.py"""
import json, os, pathlib, sys, requests
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from flask import Flask, render_template, request, redirect, url_for, abort
from jinja2 import DictLoader
from agent_glass import loop
from agent_glass.replay import replay

app = Flask(__name__)
TRACES = pathlib.Path("traces")

def models():
    try:
        return [m["name"] for m in requests.get("http://localhost:11434/api/tags", timeout=2).json()["models"]]
    except Exception:
        return None

def load(name):
    p = TRACES / pathlib.Path(name).name
    if not p.exists(): abort(404)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

def cause(e):
    v, err = e.get("validation") or {}, (e.get("validation") or {}).get("error") or ""
    if v.get("ok") is False:
        return ("MODEL" if err.startswith(("parse", "unknown tool")) else "ARGUMENTS", err)
    if e.get("tool_error"): return ("TOOL", e["tool_error"])
    if e.get("stop_reason") == "repeated_call": return ("LOOP", "same tool call repeated")
    return None

def info(events, name=""):
    start = next((e for e in events if e.get("event") == "run_start"), {})
    prev, steps = start.get("ts"), []
    for e in events:
        if e.get("event") != "step": continue
        s = dict(e); s["ms"] = round((e["ts"] - prev) * 1000) if prev and e.get("ts") else 0
        prev = e.get("ts", prev); s["cause"] = cause(s); steps.append(s)
    stop = next((e["stop_reason"] for e in reversed(events) if e.get("stop_reason")), "unknown")
    ans = next((s["parsed_call"]["final"] for s in reversed(steps)
                if isinstance(s.get("parsed_call"), dict) and "final" in s["parsed_call"]), None)
    bad = sum(1 for s in steps if s["cause"])
    return dict(name=name, task=start.get("task", "?"), model=start.get("model", "?"), steps=steps,
                n=len(steps), bad=bad, stop=stop, answer=ans, ok=stop == "final_answer",
                ms=sum(s["ms"] for s in steps), first=next((s["cause"] for s in steps if s["cause"]), None))

def diverge(a, b):
    for i in range(min(a["n"], b["n"])):
        x, y = a["steps"][i], b["steps"][i]
        if json.dumps(x.get("parsed_call"), sort_keys=True) != json.dumps(y.get("parsed_call"), sort_keys=True) \
           or bool(x["cause"]) != bool(y["cause"]):
            return i + 1
    return None if a["n"] == b["n"] else min(a["n"], b["n"]) + 1

def runs():
    return [info(load(p.name), p.name) for p in sorted(TRACES.glob("*.jsonl"), reverse=True)] if TRACES.exists() else []

T = {}
T["base"] = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Agent Glass</title><style>
:root{--p:#7C3AED;--pd:#6D28D9;--pt:#EDE9FE;--bd:#E4E7F1;--bp:#DDD6FE;--tx:#111827;--t2:#4B5563;--t3:#9CA3AF}
*{box-sizing:border-box}body{margin:0;background:#F8F9FC;color:var(--tx);font:14px/20px Geist,ui-sans-serif,system-ui,"Segoe UI",sans-serif}
.m,code,pre,.tag,h5{font-family:"JetBrains Mono",ui-monospace,Consolas,monospace}
header{background:#fff;border-bottom:1px solid var(--bp);height:56px;display:flex;align-items:center;gap:24px;padding:0 24px;position:sticky;top:0;z-index:9}
header b{color:var(--pd);letter-spacing:.06em;font-size:13px}header a{color:var(--t2);text-decoration:none;font-size:13px}header a:hover,.lk{color:var(--p)}
.pill{margin-left:auto;font-size:12px;padding:3px 10px;border-radius:99px;border:1px solid #A7F3D0;background:#ECFDF5;color:#065F46}.pill.x{border-color:#FECDD3;background:#FFF1F2;color:#9F1239}
main{max-width:1280px;margin:0 auto;padding:24px}
.card{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:14px 16px;margin:0 0 12px;box-shadow:0 1px 3px rgba(17,24,39,.03)}
.card:hover{border-color:var(--bp)}.fail{border-left:3px solid #E11D48}.good{border-left:3px solid #059669}
.ch{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding-bottom:8px;border-bottom:1px solid #F1F3F9;margin-bottom:8px}.right{margin-left:auto}.t3{color:var(--t3)}
.tag{display:inline-block;font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;padding:2px 8px;border-radius:4px;background:#F1F3F9;color:var(--t2);border:1px solid var(--bd)}
.tag.p{background:var(--pt);color:var(--pd);border-color:#C4B5FD}.tag.g{background:#ECFDF5;color:#065F46;border-color:#A7F3D0}
.tag.r{background:#FFF1F2;color:#9F1239;border-color:#FECDD3}.tag.w{background:#FFFBEB;color:#92400E;border-color:#FDE68A}
.why{background:#FFF1F2;border:1px solid #FECDD3;color:#9F1239;border-radius:6px;padding:8px 10px;margin:6px 0;font-size:13px}
pre{background:#F8F9FC;border:1px solid var(--bd);border-radius:6px;padding:8px 10px;margin:4px 0;white-space:pre-wrap;word-break:break-word;overflow-x:auto}
h5{margin:10px 0 2px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--t3)}h1,h2,h3{margin:0 0 8px;letter-spacing:-.02em}
input[type=text],select{padding:9px 12px;border:1px solid var(--bd);border-radius:6px;font:inherit;background:#fff}
input[type=text]:focus,select:focus{outline:0;border-color:var(--p);box-shadow:0 0 0 3px rgba(124,58,237,.12)}
button,.btn{background:var(--p);color:#fff;border:0;padding:9px 16px;border-radius:6px;font:600 14px Geist,system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block}
button:hover{background:var(--pd)}button:disabled{opacity:.5}.sec{background:#fff;color:var(--p);border:1px solid var(--bp)}.sec:hover{background:var(--pt)}
.chip{font-size:12px;padding:3px 10px;border:1px solid var(--bp);border-radius:99px;background:#fff;color:var(--pd);cursor:pointer}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
@media(max-width:900px){.g2{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse}td,th{padding:8px 10px;border-bottom:1px solid #F1F3F9;text-align:left}th{font-size:11px;color:var(--t3);text-transform:uppercase}
tr:hover td{background:#F5F3FF}summary{cursor:pointer;color:var(--p);font-weight:600;margin-top:8px}
.bar{height:10px;background:#EEF1FF;border-radius:99px;overflow:hidden;margin:3px 0}.bar i{display:block;height:100%;border-radius:99px}
.alert{border-left:4px solid #E11D48;background:#FFF1F2;border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:16px}.alert.ok{border-color:#059669;background:#ECFDF5}
</style></head><body><header><b>&#9670; AGENT GLASS</b><a href="/">Runs</a>
<span class="pill {{ '' if up else 'x' }}">{{ 'Ollama connected' if up else 'Ollama not detected - start the Ollama app' }}</span></header>
<main>{% block body %}{% endblock %}</main>
<script>
function openAll(v){document.querySelectorAll('details').forEach(d=>d.open=v)}
</script></body></html>"""

T["m"] = """{% macro step(e) %}<article class="card {{ 'fail' if e.cause else 'good' }}">
<div class=ch><span class="tag p">Step {{ e.step }}</span>
{% if e.cause %}<span class="tag r">{{ e.cause[0] }}</span>{% endif %}
{% if e.validation %}<span class="tag {{ 'g' if e.validation.ok else 'r' }}">validation {{ 'ok' if e.validation.ok else 'failed' }}</span>{% endif %}
{% if e.edited_by_user %}<span class="tag w">edited</span>{% endif %}
{% if e.stop_reason %}<span class=tag>{{ e.stop_reason }}</span>{% endif %}
<span class="m t3 right">{{ e.ms }} ms</span></div>
{% if e.cause %}<div class=why><b>{{ e.cause[0] }}:</b> {{ e.cause[1] }}</div>{% endif %}
<h5>Model output (raw)</h5><pre>{{ e.raw_output or '' }}</pre>
{% if e.tool_args is defined %}<h5>Tool run - {{ e.duration_ms }} ms</h5><pre>args:   {{ e.tool_args|tojson }}
result: {{ e.tool_result }}
error:  {{ e.tool_error }}</pre>{% endif %}
<details><summary>Exact prompt the model saw ({{ (e.messages_sent or [])|length }} messages)</summary>
{% for m in e.messages_sent or [] %}<h5>{{ m.role }}</h5><pre>{{ m.content }}</pre>{% endfor %}</details></article>{% endmacro %}"""

T["index"] = """{% extends 'base' %}{% block body %}
<div class=card><h3>Run the agent</h3>
<form method=post action=/run onsubmit="b=this.querySelector('button');b.disabled=true;b.textContent='Running... (can take a minute)'">
<input type=text id=task name=task style="width:100%;margin-bottom:8px" placeholder="Type a task..." required>
<div class=row><select name=model>{% for m in models or ['qwen2.5:7b'] %}<option>{{ m }}</option>{% endfor %}</select><button>Run</button>
<span class="t3">Try:</span>
{% for t in ['What is 23*47?','How many lines are in notes.txt?','What is the weather in Nashik now?','Use the tool called weather to get the temperature in Nashik'] %}
<span class=chip onclick="task.value=this.textContent">{{ t }}</span>{% endfor %}</div></form>
{% if err %}<div class=why>{{ err }}</div>{% endif %}</div>
<div class="row" style="margin:16px 0 8px"><h3 style="margin:0">Past runs</h3>
<input type=text id=q placeholder="search..." oninput="f()"><label><input type=checkbox id=bad onchange="f()"> failed only</label>
<form action=/compare class=right id=cf><input type=hidden name=a><input type=hidden name=b><button class=sec disabled id=cb>Compare 2 selected</button></form></div>
<div class=card style="padding:0"><table id=t><tr><th><th>Task<th>Model<th>Steps<th>Failed<th>Time<th>Stop</tr>
{% for r in runs %}<tr data-bad="{{ 1 if r.bad or not r.ok else 0 }}" data-n="{{ r.name }}">
<td><input type=checkbox onchange="s()"><td><a class=lk href="/trace/{{ r.name }}"><b>{{ r.task }}</b></a>
<td class=m>{{ r.model }}<td class=m>{{ r.n }}<td><span class="tag {{ 'r' if r.bad else 'g' }}">{{ r.bad }}</span>
<td class=m>{{ r.ms }} ms<td><span class="tag {{ 'g' if r.ok else 'r' }}">{{ r.stop }}</span></tr>
{% else %}<tr><td colspan=7>No runs yet - type a task above.</tr>{% endfor %}</table></div>
<script>
function f(){const k=q.value.toLowerCase();document.querySelectorAll('#t tr[data-n]').forEach(r=>r.style.display=
(r.textContent.toLowerCase().includes(k)&&(!bad.checked||r.dataset.bad=='1'))?'':'none')}
function s(){const c=[...document.querySelectorAll('#t input:checked')].map(i=>i.closest('tr').dataset.n);
cb.disabled=c.length!=2;cf.a.value=c[0]||'';cf.b.value=c[1]||''}
</script>{% endblock %}"""

T["trace"] = """{% extends 'base' %}{% from 'm' import step %}{% block body %}
<a class=lk href="/">&larr; all runs</a>
<div class="card {{ 'good' if r.ok else 'fail' }}" style="margin-top:8px"><h2>{{ r.task }}</h2>
<div class=row><span class="tag p">{{ r.model }}</span><span class=tag>{{ r.n }} steps</span><span class="tag {{ 'r' if r.bad else 'g' }}">{{ r.bad }} failed</span>
<span class="tag {{ 'g' if r.ok else 'r' }}">stop: {{ r.stop }}</span><span class=tag>{{ r.ms }} ms</span>
{% if r.first %}<span class="tag r">first failure: {{ r.first[0] }}</span>{% endif %}</div>
{% if r.answer %}<h5>Final answer</h5><pre>{{ r.answer }}</pre>{% endif %}
<div class=row style="margin-top:10px">
<form method=post action="/replay/{{ r.name }}"><button class=sec title="Reproduce this run from the recording, no model">Replay (no model)</button></form>
<form action=/compare class=row><input type=hidden name=a value="{{ r.name }}"><select name=b>{% for o in others %}<option value="{{ o.name }}">{{ o.task[:40] }} - {{ o.model }}</option>{% endfor %}</select><button class=sec>Compare with</button></form>
<button class=sec onclick="openAll(true)">Expand all</button><button class=sec onclick="openAll(false)">Collapse all</button></div></div>
{% for e in r.steps %}{{ step(e) }}{% endfor %}{% endblock %}"""

T["compare"] = """{% extends 'base' %}{% from 'm' import step %}{% block body %}
<a class=lk href="/">&larr; all runs</a><h2 style="margin-top:8px">Compare runs</h2>
{% if d %}<div class=alert><b>Runs diverge at step {{ d }}.</b>
{% for x,l in ((a,'A'),(b,'B')) %}<div class=m>{{ l }}: {{ x.steps[d-1].cause[0] ~ ' - ' ~ x.steps[d-1].cause[1] if x.n>=d and x.steps[d-1].cause else ('step ' ~ d ~ ' ok' if x.n>=d else 'ended before step ' ~ d) }}</div>{% endfor %}</div>
{% else %}<div class="alert ok"><b>No divergence:</b> both runs made the same decisions.</div>{% endif %}
<div class=g2>{% for x,l in ((a,'A'),(b,'B')) %}<div class="card {{ 'good' if x.ok else 'fail' }}">
<div class=row><span class="tag p">Trace {{ l }}</span><span class="tag {{ 'g' if x.ok else 'r' }}">{{ x.stop }}</span></div>
<h3 style="margin-top:8px"><a class=lk href="/trace/{{ x.name }}">{{ x.task }}</a></h3>
<div class="m t3">{{ x.model }} - {{ x.n }} steps - {{ x.bad }} failed - {{ x.ms }} ms</div>
{% if x.answer %}<pre>{{ x.answer }}</pre>{% endif %}</div>{% endfor %}</div>
<div class=card><h3>Latency per step</h3>{% set mx = [1] %}{% for x in (a,b) %}{% for s in x.steps %}{% if s.ms > mx[0] %}{% set _ = mx.insert(0, s.ms) %}{% endif %}{% endfor %}{% endfor %}
{% for i in range([a.n,b.n]|max) %}<div class="m t3">Step {{ i+1 }}</div>
{% for x,c in ((a,'#FB7185'),(b,'#7C3AED')) %}<div class=bar><i style="width:{{ (x.steps[i].ms*100/mx[0])|round if i < x.n else 0 }}%;background:{{ c }}"></i></div>{% endfor %}{% endfor %}
<div class="m t3">pink = A, purple = B</div></div>
<div class=row style="margin-bottom:8px"><button class=sec onclick="openAll(true)">Expand all</button><button class=sec onclick="openAll(false)">Collapse all</button></div>
<div class=g2><div>{% for e in a.steps %}{{ step(e) }}{% endfor %}</div><div>{% for e in b.steps %}{{ step(e) }}{% endfor %}</div></div>{% endblock %}"""

app.jinja_loader = DictLoader(T)
app.jinja_env.autoescape = True  # escape model output (templates have no .html suffix)

@app.route("/")
def index(err=None):
    m = models()
    return render_template("index", runs=runs(), models=m, up=m is not None, err=err)

@app.route("/run", methods=["POST"])
def run():
    try:
        _, path = loop.run(request.form["task"], request.form["model"])
    except Exception as e:
        return index(f"Run failed: {e}")
    return redirect(url_for("trace", name=pathlib.Path(path).name))

@app.route("/replay/<name>", methods=["POST"])
def do_replay(name):
    try:
        _, path = replay(str(TRACES / pathlib.Path(name).name))
    except Exception as e:
        return index(f"Replay failed (needs a complete trace): {e}")
    return redirect(url_for("trace", name=pathlib.Path(path).name))

@app.route("/trace/<name>")
def trace(name):
    r = info(load(name), name)
    return render_template("trace", r=r, others=[o for o in runs() if o["name"] != name], up=models() is not None)

@app.route("/compare")
def compare():
    a, b = info(load(request.args["a"]), request.args["a"]), info(load(request.args["b"]), request.args["b"])
    return render_template("compare", a=a, b=b, d=diverge(a, b), up=models() is not None)

if __name__ == "__main__":
    app.run(debug=False, threaded=False)