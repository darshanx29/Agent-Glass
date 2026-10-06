import ast, operator, pathlib, requests

TOOLS = {}
TYPES = {"string": str, "number": (int, float)}

def tool(name, description, params):
    def deco(fn):
        TOOLS[name] = {"fn": fn, "description": description, "params": params}
        return fn
    return deco

def describe_tools():
    lines = []
    for name, t in TOOLS.items():
        lines.append(f"- {name}({', '.join(f'{k}: {v}' for k, v in t['params'].items())}): {t['description']}")
    return "\n".join(lines)

def validate_args(name, args):
    """Return an error string, or None if the call is valid."""
    if name not in TOOLS:
        return f"unknown tool '{name}'. Available: {list(TOOLS)}"
    if not isinstance(args, dict):
        return "args must be a JSON object"
    params = TOOLS[name]["params"]
    missing = [k for k in params if k not in args]
    extra = [k for k in args if k not in params]
    if missing:
        return f"missing arguments: {missing}"
    if extra:
        return f"unexpected arguments: {extra}"
    for k, kind in params.items():
        if not isinstance(args[k], TYPES[kind]):
            return f"argument '{k}' must be {kind}, got {type(args[k]).__name__}"
    return None

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")

@tool("calculator", "Evaluate an arithmetic expression like 23*47", {"expression": "string"})
def calculator(expression):
    return _eval(ast.parse(expression, mode="eval").body)

WORKSPACE = pathlib.Path("workspace").resolve()

@tool("read_file", "Read a text file from the workspace folder", {"path": "string"})
def read_file(path):
    p = (WORKSPACE / path).resolve()
    if WORKSPACE not in p.parents:
        raise ValueError("path is outside the workspace")
    return p.read_text(encoding="utf-8")[:4000]

@tool("fetch_url", "Download a web page and return the first 2000 characters", {"url": "string"})
def fetch_url(url):
    return requests.get(url, timeout=10).text[:2000]

@tool("get_weather", "Get the current weather for a city", {"city": "string"})
def get_weather(city):
    geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                       params={"name": city, "count": 1}, timeout=10).json()
    if not geo.get("results"):
        raise ValueError(f"city '{city}' not found")
    place = geo["results"][0]
    w = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current_weather": True}, timeout=10).json()["current_weather"]
    return f"{place['name']}: {w['temperature']} C, wind {w['windspeed']} km/h"