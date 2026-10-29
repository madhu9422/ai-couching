"""LLM integration (Gemini). Handles prompting, JSON parsing, retries and validation."""
import json
import os
import re
import time

from dotenv import load_dotenv

import code_manager as cm
import learning_plan as lp
import quiz_manager as qm

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
SYSTEM_INSTRUCTION = (
    "You are a careful, encouraging learning coach. Follow the requested output format exactly. "
    "Never claim a learner has mastered a topic based on a single short quiz."
)


class AIServiceError(Exception):
    """Any failure talking to the LLM, with a message safe to show the user."""


class MissingAPIKeyError(AIServiceError):
    pass


class InvalidResponseError(AIServiceError):
    pass


def parse_json(text: str):
    """Extract a JSON object from model output (tolerates ```json fences / stray text)."""
    if not text or not text.strip():
        raise ValueError("The model returned an empty response.")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("The model's reply did not contain valid JSON.")
        return json.loads(cleaned[start:end + 1])  # JSONDecodeError is a ValueError


_SKIP_WORDS = ("image", "tts", "live", "audio", "embedding", "robotics", "computer", "vision", "veo", "imagen")


def _is_not_found(exc) -> bool:
    m = str(exc)
    return "404" in m or "NOT_FOUND" in m


def _is_auth_error(exc) -> bool:
    m = str(exc).lower()
    return any(w in m for w in ("api key not valid", "api_key_invalid", "permission_denied", "401", "403"))


class AIService:
    def __init__(self, api_key=None, model=None, max_attempts=3, api_retries=1, timeout_seconds=None,
                 fallback_models=None, auto_fallback=True):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.max_attempts = max_attempts   # tries when the reply fails validation
        self.api_retries = api_retries     # extra tries per model when the API call itself fails
        self.timeout_seconds = timeout_seconds or int(os.getenv("GEMINI_TIMEOUT", "90"))
        if fallback_models is None:
            fallback_models = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
        self.fallback_models = fallback_models
        self.auto_fallback = auto_fallback  # discover other flash models if the chosen one keeps failing
        self._client = None
        self._variant = 0

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=self.timeout_seconds * 1000),  # milliseconds
            )
        return self._client

    def list_flash_models(self) -> list:
        """Names of available text models that look fast (flash-lite first). Empty list on any failure."""
        try:
            names = []
            for m in self._get_client().models.list():
                name = (m.name or "").replace("models/", "")
                actions = getattr(m, "supported_actions", None) or []
                if "flash" in name and "generateContent" in actions and not any(w in name for w in _SKIP_WORDS):
                    names.append(name)
            return sorted(set(names), key=lambda n: ("lite" not in n, n))
        except Exception:
            return []

    def _model_candidates(self):
        seen = set()
        for m in [self.model] + list(self.fallback_models):
            if m not in seen:
                seen.add(m)
                yield m
        if self.auto_fallback:
            for m in self.list_flash_models()[:3]:
                if m not in seen:
                    seen.add(m)
                    yield m

    # ---- low-level call -------------------------------------------------
    def _call_model(self, prompt: str, json_mode: bool = True, model: str = None) -> str:
        if not self.has_api_key:
            raise MissingAPIKeyError(
                "No API key found. Copy .env.example to .env and set GEMINI_API_KEY, then restart the app."
            )
        from google.genai import types

        client = self._get_client()
        model = model or self.model
        variants = [None]
        if os.getenv("GEMINI_THINKING", "minimal").lower() != "default":
            # Less "thinking" = much faster replies. Fall back if a model rejects the setting.
            variants = [types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                        types.ThinkingConfig(thinking_budget=0), None]
        text = ""
        for idx in range(min(self._variant, len(variants) - 1), len(variants)):
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.4,
                response_mime_type="application/json" if json_mode else "text/plain",
                thinking_config=variants[idx],
            )
            try:
                # Streaming returns the first bytes quickly, which avoids long-request 504 timeouts.
                stream = client.models.generate_content_stream(model=model, contents=prompt, config=config)
                text = "".join((chunk.text or "") for chunk in stream)
                self._variant = idx
                break
            except Exception as exc:
                msg = str(exc).lower()
                if idx < len(variants) - 1 and any(w in msg for w in ("thinking", "budget", "level")):
                    continue
                raise
        if not text.strip():
            raise RuntimeError("empty response")
        return text

    def _call_with_retries(self, prompt: str, json_mode: bool = True) -> str:
        last, tried = None, []
        for model in self._model_candidates():
            tried.append(model)
            for attempt in range(self.api_retries + 1):
                try:
                    text = self._call_model(prompt, json_mode, model)
                    self.model = model  # remember the model that worked
                    return text
                except MissingAPIKeyError:
                    raise
                except Exception as exc:  # network, quota, overload, timeouts ...
                    last = exc
                    if _is_auth_error(exc):
                        raise AIServiceError(
                            "Google rejected your API key. Check GEMINI_API_KEY in your .env file, "
                            "then restart the app.") from exc
                    if _is_not_found(exc):
                        break  # this model is not available to you: go straight to the next one
                    if attempt < self.api_retries:
                        time.sleep(2 ** attempt)
        raise AIServiceError(
            "Could not get a response from the AI service (models tried: " + ", ".join(tried) + "). "
            "Check your internet connection, then try again, or run `python check_api.py` to find a "
            f"model that works for your key. (Details: {type(last).__name__}: {last})"
        )

    # ---- validated generation ------------------------------------------
    def _generate_validated(self, prompt: str, validator):
        last_error = None
        for _ in range(self.max_attempts):
            p = prompt
            if last_error:
                p += f"\n\nYour previous reply was rejected: {last_error}\nReturn corrected JSON only."
            text = self._call_with_retries(p)
            try:
                return validator(parse_json(text))
            except ValueError as exc:  # JSON errors + Plan/QuizValidationError
                last_error = str(exc)
        raise InvalidResponseError(
            f"The AI returned an invalid response {self.max_attempts} times ({last_error}). Please try again."
        )

    def generate_plan(self, profile: dict) -> dict:
        return self._generate_validated(
            lp.build_plan_prompt(profile), lambda data: lp.validate_plan(data, profile)
        )

    def generate_quiz(self, subject, level, topic, objectives, last_percentage=None) -> list:
        prompt = qm.build_quiz_prompt(subject, level, topic, objectives, last_percentage)
        return self._generate_validated(prompt, qm.validate_quiz)

    def generate_exercise(self, subject, level, topic, objectives, difficulty) -> dict:
        prompt = cm.build_exercise_prompt(subject, level, topic, objectives, difficulty)
        return self._generate_validated(prompt, lambda data: cm.validate_exercise(data, difficulty))

    def generate_feedback(self, subject, level, topic, details, percentage) -> str:
        """Short coaching note. Optional: returns '' on any failure so scoring never depends on it."""
        wrong = [d for d in details if not d["is_correct"]]
        if not wrong:
            return ""
        missed = "\n".join(f"- {d['question']} (correct: {d['options'][d['correct_index']]})" for d in wrong)
        prompt = (
            f"A {level} learner studying {subject} scored {percentage:.0f}% on a short quiz about '{topic}'.\n"
            f"Questions they missed:\n{missed}\n\n"
            "Write 2-4 sentences of encouraging, specific advice on what to review and how to practise. "
            "Do not claim mastery or give a score. Plain text only."
        )
        try:
            return self._call_with_retries(prompt, json_mode=False).strip()
        except AIServiceError:
            return ""
