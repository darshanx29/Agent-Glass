import requests

URL = "http://localhost:11434/v1/chat/completions"

def chat(messages, model="qwen2.5:3b", temperature=0.0):
    r = requests.post(URL, json={
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]