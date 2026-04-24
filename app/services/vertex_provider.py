import httpx

from app.config import settings


class VertexProvider:
    name = "vertex"

    def __init__(self) -> None:
        missing = [
            name
            for name, value in {
                "VERTEX_PROJECT_ID": settings.vertex_project_id,
                "VERTEX_LOCATION": settings.vertex_location,
                "VERTEX_ENDPOINT_ID": settings.vertex_endpoint_id,
                "VERTEX_ACCESS_TOKEN": settings.vertex_access_token,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Vertex configuration incomplete: {', '.join(missing)}")

    def analyze_chart(self, context: dict) -> dict:
        return self._predict("chart", context)

    def generate_report(self, context: dict) -> dict:
        return self._predict("report", context)

    def chat(self, context: dict, message: str) -> dict:
        raise RuntimeError("Chat intentionally stays on Gemini, not Vertex.")

    def _predict(self, task: str, context: dict) -> dict:
        # The endpoint is expected to be a custom trained Vertex model that
        # accepts one compact JSON instance and returns one schema-compatible
        # prediction. Hard metrics are already computed before this call.
        url = (
            f"https://{settings.vertex_location}-aiplatform.googleapis.com/v1/"
            f"projects/{settings.vertex_project_id}/locations/{settings.vertex_location}/"
            f"endpoints/{settings.vertex_endpoint_id}:predict"
        )
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.vertex_access_token}"},
            json={"instances": [{"task": task, "context": context}]},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        predictions = payload.get("predictions") or []
        if not predictions:
            raise ValueError("Vertex response did not contain predictions.")
        prediction = predictions[0]
        if isinstance(prediction, dict) and "result" in prediction:
            return prediction["result"]
        return prediction
