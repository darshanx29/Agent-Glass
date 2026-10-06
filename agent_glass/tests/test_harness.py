import json, itertools, pytest
from agent_glass import loop
from agent_glass.tools import validate_args, TOOLS
from agent_glass.loop import parse

# ---------- validation ----------
def test_unknown_tool():
    assert "unknown tool" in validate_args("weather", {})

def test_missing_arg():
    assert "missing" in validate_args("calculator", {})

def test_extra_arg():
    assert "unexpected" in validate_args("calculator", {"expression": "1+1", "x": 1})

def test_wrong_type():
    assert "must be string" in validate_args("calculator", {"expression": 5})

def test_valid_call():
    assert validate_args("calculator", {"expression": "1+1"}) is None

# ---------- tools ----------
def test_calculator():
    assert TOOLS["calculator"]["fn"]("23*47") == 1081

def test_calculator_rejects_code():
    with pytest.raises(ValueError):
        TOOLS["calculator"]["fn"]("__import__('os').getcwd()")

def test_read_file_blocks_outside_workspace():
    with pytest.raises(ValueError):
        TOOLS["read_file"]["fn"]("../LICENSE")

# ---------- parsing ----------
def test_parse_clean():
    assert parse('{"final": "ok"}') == {"final": "ok"}

def test_parse_wrapped_in_text():
    assert parse('Sure! {"final": "ok"} done') == {"final": "ok"}

def test_parse_garbage():
    with pytest.raises(Exception):
        parse("no json here")

# ---------- loop with a fake model ----------
def fake(replies):
    it = iter(replies)
    return lambda messages, model: next(it)

def events(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]

def test_loop_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loop, "chat", fake([
        '{"tool": "calculator", "args": {"expression": "23*47"}}',
        '{"final": "1081"}']))
    answer, path = loop.run("What is 23*47?")
    assert answer == "1081"
    assert events(path)[-1]["stop_reason"] == "final_answer"

def test_loop_recovers_from_unknown_tool(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loop, "chat", fake([
        '{"tool": "weather", "args": {}}',
        '{"final": "sorry"}']))
    answer, path = loop.run("weather?")
    steps = [e for e in events(path) if e.get("event") == "step"]
    assert steps[0]["validation"]["ok"] is False
    assert answer == "sorry"

def test_loop_detects_repeated_call(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    same = '{"tool": "calculator", "args": {"expression": "1+1"}}'
    monkeypatch.setattr(loop, "chat", fake(itertools.repeat(same)))
    answer, path = loop.run("loop forever")
    assert answer is None
    assert events(path)[-1]["stop_reason"] == "repeated_call"

def test_loop_hits_step_limit(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loop, "chat", fake(itertools.repeat("not json")))
    answer, path = loop.run("anything", max_steps=3)
    assert answer is None
    assert events(path)[-1]["stop_reason"] == "max_steps"