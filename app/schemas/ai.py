from pydantic import BaseModel, Field


# These models are the contract for every AI provider.
# Gemini/Vertex/local providers may interpret data, but responses must validate here
# before values are returned to the API.
class ForecastPoint(BaseModel):
    # x must match one chart bucket from the deterministic backend x_axis.
    x: str
    predicted_energy: float = Field(ge=0)
    predicted_co2: float = Field(ge=0)
    optimized_energy: float = Field(ge=0)
    optimized_co2: float = Field(ge=0)


class ChartAIResult(BaseModel):
    provider: str
    points: list[ForecastPoint]
    # Text fields are allowed to be interpretive, but not used for hard math.
    explanations: list[str] = Field(default_factory=list)
    influencing_factors: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    fallback_used: bool = False


class ReportAIResult(BaseModel):
    provider: str
    title: str
    overview: str
    main_findings: list[str] = Field(default_factory=list)
    influencing_factors: list[str] = Field(default_factory=list)
    forecast_notes: list[str] = Field(default_factory=list)
    optimization_notes: list[str] = Field(default_factory=list)
    risks_and_uncertainties: list[str] = Field(default_factory=list)
    plain_text_report: str
    fallback_used: bool = False


class ChatAIResult(BaseModel):
    provider: str
    answer: str
    referenced_metrics: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    fallback_used: bool = False
