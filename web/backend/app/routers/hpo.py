"""HPO extraction endpoints."""
from fastapi import APIRouter, HTTPException
from app.models.schemas import HPOExtractionRequest, HPOExtractionResponse, HPOTerm
from app.services.hpo_service import extract_hpo_from_text

router = APIRouter(prefix="/api/hpo", tags=["HPO Extraction"])


@router.post("/extract", response_model=HPOExtractionResponse)
async def extract_hpo(request: HPOExtractionRequest):
    """Extract HPO terms from free-text clinical description."""
    if not request.clinical_text.strip():
        raise HTTPException(status_code=400, detail="Clinical text is required")

    try:
        result = await extract_hpo_from_text(
            clinical_text=request.clinical_text,
            openai_api_key=request.api_key,
        )
        return HPOExtractionResponse(
            phenotypes=[HPOTerm(**p) for p in result["phenotypes"]],
            raw_extraction=result["raw_extraction"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HPO extraction failed: {str(e)}")
