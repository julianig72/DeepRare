from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ProviderEnum(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    deepseek = "deepseek"


# --- Request schemas ---

class HPOExtractionRequest(BaseModel):
    clinical_text: str = Field(..., description="Free-text clinical description")
    api_key: Optional[str] = Field(None, description="OpenAI API key (overrides server default)")


class DiagnosisRequest(BaseModel):
    clinical_text: str = Field("", description="Free-text clinical description")
    phenotypes: list[str] = Field(default_factory=list, description="List of phenotype descriptions")
    phenotype_ids: list[str] = Field(default_factory=list, description="List of HPO IDs (e.g. HP:0001250)")
    model: str = Field("gpt-4o", description="LLM model ID")
    provider: ProviderEnum = Field(ProviderEnum.openai, description="LLM provider")
    api_key: Optional[str] = Field(None, description="API key for the selected provider")
    openai_api_key: Optional[str] = Field(None, description="OpenAI key (always needed for embeddings)")
    search_engine: str = Field("duckduckgo", description="Web search engine: bing, google, duckduckgo")


class GeneDiagnosisRequest(BaseModel):
    clinical_text: str = Field("", description="Free-text clinical description")
    phenotypes: list[str] = Field(default_factory=list, description="List of phenotype descriptions")
    phenotype_ids: list[str] = Field(default_factory=list, description="List of HPO IDs")
    model: str = Field("gpt-4o", description="LLM model ID")
    provider: ProviderEnum = Field(ProviderEnum.openai, description="LLM provider")
    api_key: Optional[str] = Field(None, description="API key for the selected provider")
    openai_api_key: Optional[str] = Field(None, description="OpenAI key (always needed for embeddings)")
    search_engine: str = Field("duckduckgo", description="Web search engine")


class ValidateKeyRequest(BaseModel):
    provider: ProviderEnum
    api_key: str


# --- Response schemas ---

class HPOTerm(BaseModel):
    phenotype_text: str
    hpo_code: str
    hpo_description: str
    similarity: float


class HPOExtractionResponse(BaseModel):
    phenotypes: list[HPOTerm]
    raw_extraction: str


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


class ValidateKeyResponse(BaseModel):
    valid: bool
    message: str


class DiagnosisStep(BaseModel):
    step: str
    status: str  # "running", "completed", "error"
    detail: Optional[str] = None
    data: Optional[dict] = None


class DiseaseResult(BaseModel):
    rank: int
    disease_name: str
    orphanet_id: Optional[str] = None
    confidence: Optional[str] = None
    evidence_summary: Optional[str] = None


class DiagnosisResponse(BaseModel):
    diseases: list[DiseaseResult]
    raw_diagnosis: Optional[str] = None
    web_evidence: Optional[str] = None
    similar_cases: Optional[list[dict]] = None
    reflection: Optional[str] = None
    final_diagnosis: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    deeprare_available: bool
