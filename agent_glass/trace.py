import json, pathlib, time, uuid

class Trace:
    def __init__(self, task, model, directory="traces"):
        pathlib.Path(directory).mkdir(exist_ok=True)
        self.run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        self.path = pathlib.Path(directory) / f"{self.run_id}.jsonl"
        self.emit({"event": "run_start", "task": task, "model": model})

    def emit(self, event):
        event = {"run_id": self.run_id, "ts": time.time(), **event}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")