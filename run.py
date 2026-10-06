import os, sys, time, shutil, subprocess, threading, webbrowser, requests

os.chdir(os.path.dirname(os.path.abspath(__file__)))
OLLAMA = "http://localhost:11434"
URL = "http://127.0.0.1:5000"

def models():
    try:
        r = requests.get(OLLAMA + "/api/tags", timeout=2).json()
        return [m["name"] for m in r["models"]]
    except Exception:
        return None

def ensure_ollama():
    if models() is not None:
        print("[ok] Ollama is running")
    elif not shutil.which("ollama"):
        print("[!!] Ollama is not installed. Install it from ollama.com")
        return
    else:
        print("[..] Starting Ollama...")
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        for _ in range(20):
            if models() is not None:
                print("[ok] Ollama started")
                break
            time.sleep(1)
        else:
            print("[!!] Could not start Ollama. Open the Ollama app manually.")
            return
    found = models() or []
    print("[ok] Models:", ", ".join(found) if found else "none (run: ollama pull qwen2.5:7b)")

def run_tests():
    print("[..] Running tests...")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"])
    print("[ok] Tests passed" if r.returncode == 0 else "[!!] Some tests failed (continuing)")

def demo():
    from agent_glass import loop
    from agent_glass.replay import replay
    model = (models() or ["qwen2.5:7b"])[0]
    print(f"\n[demo] Running a task on {model}")
    answer, path = loop.run("What is 23*47?", model)
    print("Answer:", answer, "| Trace:", path)
    print("[demo] Replaying it with no model")
    print("Replayed:", replay(str(path))[0])

if __name__ == "__main__":
    print("=== Agent Glass ===")
    ensure_ollama()
    if "--skip-tests" not in sys.argv:
        run_tests()
    if "--demo" in sys.argv:
        demo()
    threading.Timer(2.5, lambda: webbrowser.open(URL)).start()
    print(f"[ok] Opening {URL}  (press Ctrl+C to stop)")
    subprocess.call([sys.executable, "viewer/app.py"])