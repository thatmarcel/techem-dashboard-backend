import json
import re


import httpx

from app.config import settings


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not configured.")
        self.model = settings.google_ai_model or "gemini-1.5-flash"

    def _generate_json(
        self,
        task: str,
        context: dict,
        schema_hint: dict,
        *,
        system_instruction: str | None = None,
        user_message: str | None = None,
    ) -> dict:
        system_text = system_instruction or (
            "Du bist ein vorsichtiger Energieanalyse-Assistent. Nutze nur die gelieferten Daten. "
            "Erfinde keine harten Kennzahlen. Antworte ausschliesslich als valides JSON im Schema."
        )
        prompt = {
            "task": task,
            "schema": schema_hint,
            "context": context,
        }
        if user_message:
            prompt["user_message"] = user_message
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": settings.google_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_text}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}],
            },
            timeout=20,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(_extract_json(text))

    def analyze_chart(self, context: dict) -> dict:
        return self._generate_json(
            "forecast_and_optimization",
            context,
            {
                "provider": "gemini",
                "points": [
                    {
                        "x": "same x label as input",
                        "predicted_energy": "number",
                        "predicted_co2": "number",
                        "optimized_energy": "number",
                        "optimized_co2": "number",
                    }
                ],
                "explanations": ["string"],
                "influencing_factors": ["string"],
                "anomalies": ["string"],
                "fallback_used": False,
            },
        )

    def generate_report(self, context: dict) -> dict:
        return self._generate_json(
            "structured_report",
            context,
            {
                "provider": "gemini",
                "title": "string",
                "overview": "string",
                "main_findings": ["string"],
                "influencing_factors": ["string"],
                "forecast_notes": ["string"],
                "optimization_notes": ["string"],
                "risks_and_uncertainties": ["string"],
                "plain_text_report": "string",
                "fallback_used": False,
            },
        )

    def chat(self, context: dict, message: str) -> dict:
        extra_instructions = context.get("additional_instructions")
        system_prompt = build_chat_system_prompt(extra_instructions)
        return self._generate_json(
            "chat",
            context,
            {
                "provider": "gemini",
                "answer": "string",
                "referenced_metrics": ["string"],
                "caveats": ["string"],
                "fallback_used": False,
            },
            system_instruction=system_prompt,
            user_message=message,
        )


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def build_chat_system_prompt(additional_instructions: str | None) -> str:
    prompt_parts = [
        settings.google_chat_system_prompt,
        (
            "Für den Chat gilt zusätzlich: "
            "Antworte nur auf Basis des kompakten Scopes, der Zeitreihe, der Zusammenfassung, des Wetterkontexts und optionaler Datei-Auszüge. "
            "Für Fragen zum aktuellen Wetter oder zu heutigen Wettereffekten nutze zuerst current_weather und current_weather_location. "
            "weather ist die Wetterreihe zum geöffneten Chart-Zeitraum und kann aggregiert sein. "
            "Nutze Datei-Auszüge nur als Kontext, nicht als harte Messquelle, wenn die Kennzahlen bereits strukturiert vorliegen. "
            "Wenn sich die Frage nicht aus dem Kontext beantworten lässt, sage das explizit."
        ),
        (
            "Das Antwortformat muss valides JSON sein mit den Feldern: "
            "provider, answer, referenced_metrics, caveats, fallback_used."
        ),
    ]
    if additional_instructions:
        prompt_parts.append(f"Zusatzanweisungen für diesen einen Chat-Aufruf: {additional_instructions}")
    return "\n\n".join(prompt_parts)


