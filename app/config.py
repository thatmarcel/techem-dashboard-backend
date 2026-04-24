from dataclasses import dataclass
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


DEFAULT_CHAT_SYSTEM_PROMPT = (
    "Du bist ein vorsichtiger Assistent für einen Heizenergie-Chat in einem Vermieter-Dashboard. "
    "Nutze nur den bereitgestellten Kontext. Erfinde keine Kennzahlen, keine Dateien und keine Messwerte. "
    "Wenn etwas im Kontext fehlt, sage das klar. Antworte knapp, fachlich und nachvollziehbar."
)


def read_prompt_file(path_value: str | None, fallback: str) -> str:
    if not path_value:
        return fallback

    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate

    try:
        text = candidate.read_text(encoding="utf-8").strip()
        return text or fallback
    except OSError:
        return fallback


@dataclass(frozen=True)
class Settings:
    tomorrow_api_key: str = os.getenv("TOMORROW_API_KEY", "")
    weather_provider: str = os.getenv("WEATHER_PROVIDER", "auto")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_ai_provider: str = os.getenv("GOOGLE_AI_PROVIDER", "gemini")
    google_ai_model: str = os.getenv("GOOGLE_AI_MODEL", "gemini-1.5-flash")
    google_chat_system_prompt_file: str = os.getenv(
        "GOOGLE_CHAT_SYSTEM_PROMPT_FILE",
        "prompts/chat_system_prompt.txt",
    )
    google_chat_system_prompt: str = read_prompt_file(
        os.getenv("GOOGLE_CHAT_SYSTEM_PROMPT_FILE", "prompts/chat_system_prompt.txt"),
        os.getenv("GOOGLE_CHAT_SYSTEM_PROMPT", DEFAULT_CHAT_SYSTEM_PROMPT),
    )
    chart_ai_provider: str = os.getenv("CHART_AI_PROVIDER", "vertex")
    vertex_project_id: str = os.getenv("VERTEX_PROJECT_ID", "")
    vertex_location: str = os.getenv("VERTEX_LOCATION", "")
    vertex_endpoint_id: str = os.getenv("VERTEX_ENDPOINT_ID", "")
    vertex_access_token: str = os.getenv("VERTEX_ACCESS_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./demo.db")
    energy_price_eur_per_kwh: float = float(os.getenv("ENERGY_PRICE_EUR_PER_KWH", "0.12"))


settings = Settings()


def sqlite_path_from_url(database_url: str | None = None) -> Path:
    url = database_url or settings.database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError("Only sqlite:/// database URLs are supported in this demo.")

    raw_path = url[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path

