"""Diagnosis endpoints with SSE streaming."""
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse
from app.models.schemas import DiagnosisRequest
from app.services.diagnosis_service import run_diagnosis_stream, run_gene_diagnosis_stream

router = APIRouter(prefix="/api/diagnosis", tags=["Diagnosis"])


@router.post("/phenotype")
async def diagnose_phenotype(request: DiagnosisRequest):
    """Run phenotype-based rare disease diagnosis (SSE stream)."""
    if not request.clinical_text.strip() and not request.phenotypes:
        raise HTTPException(status_code=400, detail="Clinical text or phenotypes required")

    return EventSourceResponse(
        run_diagnosis_stream(
            clinical_text=request.clinical_text,
            phenotypes=request.phenotypes,
            phenotype_ids=request.phenotype_ids,
            model=request.model,
            provider=request.provider.value,
            api_key=request.api_key,
            openai_api_key=request.openai_api_key,
            search_engine=request.search_engine,
        )
    )


@router.post("/gene")
async def diagnose_gene(
    clinical_text: str = Form(""),
    phenotypes: str = Form(""),
    phenotype_ids: str = Form(""),
    model: str = Form("gpt-4o"),
    provider: str = Form("openai"),
    api_key: str = Form(""),
    openai_api_key: str = Form(""),
    search_engine: str = Form("duckduckgo"),
    vcf_file: UploadFile | None = File(None),
):
    """Run gene-aware diagnosis with optional VCF file upload (SSE stream)."""
    phenotype_list = [p.strip() for p in phenotypes.split(",") if p.strip()] if phenotypes else []
    phenotype_id_list = [p.strip() for p in phenotype_ids.split(",") if p.strip()] if phenotype_ids else []

    vcf_path = None
    if vcf_file:
        tmp_dir = Path(tempfile.mkdtemp(prefix="deeprare_vcf_"))
        vcf_path = str(tmp_dir / vcf_file.filename)
        with open(vcf_path, "wb") as f:
            shutil.copyfileobj(vcf_file.file, f)

    async def stream_and_cleanup():
        try:
            async for event in run_gene_diagnosis_stream(
                clinical_text=clinical_text,
                phenotypes=phenotype_list,
                phenotype_ids=phenotype_id_list,
                model=model,
                provider=provider,
                api_key=api_key or None,
                openai_api_key=openai_api_key or None,
                vcf_path=vcf_path,
                search_engine=search_engine,
            ):
                yield event
        finally:
            if vcf_path and Path(vcf_path).parent.exists():
                shutil.rmtree(Path(vcf_path).parent, ignore_errors=True)

    return EventSourceResponse(stream_and_cleanup())
