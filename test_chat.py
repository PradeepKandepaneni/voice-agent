import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

from prompts import build_system_prompt

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
BUSINESS = os.getenv("BUSINESS_NAME", "Acme Co")
URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent?key={API_KEY}"
)


def gemini_reply(system_prompt, history):
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": history,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        URL, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"[API error {e.code}: {e.read().decode('utf-8')[:300]}]"
    except Exception as e:
        return f"[Request failed: {e}]"
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        return f"[Unexpected response: {json.dumps(result)[:300]}]"


def main():
    if not API_KEY:
        print("No GOOGLE_API_KEY found in .env — fill it in first.")
        sys.exit(1)

    mode = ""
    while mode not in ("1", "2"):
        mode = input("Test which agent?  1 = inbound support   2 = outbound sales : ").strip()
    direction = "inbound" if mode == "1" else "outbound"

    name = reason = None
    if direction == "outbound":
        name = input("Lead's name (optional, Enter to skip): ").strip() or None
        reason = input("Reason for the call (optional, Enter to skip): ").strip() or None

    system_prompt = build_system_prompt(
        direction=direction,
        business_name=BUSINESS,
        customer_name=name,
        call_reason=reason,
    )

    print("\n--- Talking to your agent. Type 'quit' to stop. ---\n")
    history = []

    if direction == "outbound":
        history.append({"role": "user", "parts": [{"text": "(The call just connected.)"}]})
        reply = gemini_reply(system_prompt, history)
        history.append({"role": "model", "parts": [{"text": reply}]})
        print(f"AGENT: {reply}\n")

    while True:
        you = input("YOU: ").strip()
        if you.lower() in ("quit", "exit"):
            break
        if not you:
            continue
        history.append({"role": "user", "parts": [{"text": you}]})
        reply = gemini_reply(system_prompt, history)
        history.append({"role": "model", "parts": [{"text": reply}]})
        print(f"AGENT: {reply}\n")


if __name__ == "__main__":
    main()
