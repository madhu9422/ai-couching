"""Find which Gemini models work for YOUR API key and how fast they answer.

Run:  python check_api.py
Then copy the suggested GEMINI_MODEL line into your .env file and restart the app.
"""
import time

from ai_service import AIService


def main():
    svc = AIService(timeout_seconds=30, api_retries=0, auto_fallback=False)
    if not svc.has_api_key:
        print("No API key found. Put GEMINI_API_KEY=... in your .env file first.")
        return
    print("Looking up available models...")
    candidates = svc.list_flash_models()
    if not candidates:
        print("Could not list models. Check your internet connection and API key.")
        return
    print("Testing:", ", ".join(candidates[:6]), "\n")
    results = []
    for name in candidates[:6]:
        start = time.time()
        try:
            svc._call_model('Reply with exactly this JSON: {"ok": true}', True, name)
            secs = time.time() - start
            results.append((secs, name))
            print(f"  OK     {name:<40} {secs:5.1f}s")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {name:<40} {str(exc)[:70]}")
    if results:
        best = min(results)[1]
        print(f"\nFastest working model: {best}\nPut this in your .env file:\n  GEMINI_MODEL={best}")
    else:
        print("\nNo model responded. Try again in a minute, or check your key at aistudio.google.com.")


if __name__ == "__main__":
    main()
