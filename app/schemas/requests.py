from pydantic import BaseModel, Field


class ImportDirectoryRequest(BaseModel):
    directory_path: str = Field(..., description="Local directory containing CSV files.")


class ChatRequest(BaseModel):
    message: str
    use_current_scope: bool = True
    scope_type: str = "total"
    scope_id: str | None = None
    period: str = "month"
    offset: int = 0
    analysis_provider: str = "gemini"
    additional_instructions: str | None = None
    context_file_paths: list[str] = Field(default_factory=list)
