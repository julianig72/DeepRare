"""Diagnosis service - wraps diagnosis.py and diagnosisGene.py for web use."""
import re
import sys
import json
import asyncio
import traceback
from pathlib import Path
from typing import AsyncGenerator
from app.config import DEEPRARE_ROOT, settings
from app.services.model_manager import (
    create_handler, create_openai_handler, get_api_key, get_openai_key,
)


def _parse_diseases_from_markdown(text: str) -> list[dict]:
    """Extract ranked diseases with reasoning from the LLM's markdown output."""
    if not text:
        return []

    sections = re.split(r'(?=##\s+\*\*)', text)
    diseases = []
    rank = 0

    for section in sections:
        name_match = re.match(r'##\s+\*\*(.+?)\*\*\s*(?:\(Rank\s*#?(\d+))?', section)
        if not name_match:
            continue

        rank += 1
        disease_name = name_match.group(1).strip()
        explicit_rank = int(name_match.group(2)) if name_match.group(2) else rank

        reasoning = ""
        reasoning_match = re.search(
            r'###\s*Diagnostic Reasoning:\s*\n(.*?)(?=\n##\s|\n---|\Z)',
            section, re.DOTALL
        )
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
            reasoning = re.sub(r'^[-•]\s*', '', reasoning, flags=re.MULTILINE)

        diseases.append({
            "rank": explicit_rank,
            "disease_name": disease_name,
            "orphanet_id": "",
            "confidence": "",
            "evidence_summary": reasoning[:500] if reasoning else "",
        })

    if not diseases and text.strip():
        bold_names = re.findall(r'\*\*(.+?)\*\*', text)
        seen = set()
        for name in bold_names:
            clean = name.strip()
            if clean and clean not in seen and len(clean) > 3:
                seen.add(clean)
                diseases.append({
                    "rank": len(diseases) + 1,
                    "disease_name": clean,
                    "orphanet_id": "",
                    "confidence": "",
                    "evidence_summary": "",
                })
                if len(diseases) >= 5:
                    break

    return diseases

if str(DEEPRARE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEPRARE_ROOT))

_diagnosis_resources = None


class _WebArgs:
    """Minimal args namespace matching attributes used by make_diagnosis and tools."""

    def __init__(self, search_engine: str, device, exomiser_jar: str = "",
                 exomiser_save_path: str = ""):
        self.dataset_name = "web"
        self.search_engine = search_engine
        self.device = device
        self.screenshots = False
        self.exomiser_jar = exomiser_jar
        self.exomiser_save_path = exomiser_save_path
        # Tools expect these attributes
        self.results_folder = str(Path(DEEPRARE_ROOT / "result_web"))
        self.visualize = False
        self.chrome_driver = ""
        self.google_api = settings.google_cse_api_key
        self.search_engine_id = settings.google_cse_id


def _load_diagnosis_resources():
    """Load shared resources: models, Orphanet data, embeddings, similar cases."""
    global _diagnosis_resources
    if _diagnosis_resources is not None:
        return _diagnosis_resources

    import torch
    import pandas as pd
    from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification
    from data import RarePrompt

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # BioLORD model (eval_model / eval_tokenizer)
    biolord_name = "FremyCompany/BioLORD-2023-C"
    eval_tokenizer = AutoTokenizer.from_pretrained(biolord_name)
    eval_model = AutoModel.from_pretrained(biolord_name)

    # Retrieval reranker (MedCPT Cross-Encoder)
    retr_name = "ncbi/MedCPT-Cross-Encoder"
    retr_tokenizer = AutoTokenizer.from_pretrained(retr_name)
    retr_model = AutoModelForSequenceClassification.from_pretrained(retr_name)

    rare_prompt = RarePrompt()

    # Orphanet knowledge (orpha_disorders_HP_map)
    orphanet_data = {}
    p = settings.orphanet_knowledge_path
    if p and Path(p).exists():
        with open(p, "r", encoding="utf-8-sig") as f:
            orphanet_data = json.load(f)

    # Concept2ID mapping
    concept2id = {}
    p = settings.orpha_concept2id_path
    if p and Path(p).exists():
        with open(p, "r", encoding="utf-8-sig") as f:
            concept2id = json.load(f)

    # Orpha → OMIM mapping
    orpha2omim = {}
    p = settings.orpha2omim_path
    if p and Path(p).exists():
        with open(p, "r", encoding="utf-8-sig") as f:
            orpha2omim = json.load(f)

    # Pre-computed disease embeddings (aligned with concept2id)
    embeds_disease = None
    p = settings.disease_embeddings_path
    if p and Path(p).exists():
        embeds_disease = torch.load(p, map_location="cpu", weights_only=False)
        embeds_disease = torch.tensor(embeds_disease)

    # Similar cases for RAG retrieval
    similar_cases = pd.DataFrame(columns=["_id", "case_report", "embedding", "diagnosis"])
    p = settings.similar_cases_path
    if p and Path(p).exists():
        similar_cases = pd.read_csv(p)[["_id", "case_report", "embedding", "diagnosis"]]
        similar_cases = similar_cases[similar_cases["embedding"].notna()]

    _diagnosis_resources = {
        "device": device,
        "eval_model": eval_model,
        "eval_tokenizer": eval_tokenizer,
        "retr_model": retr_model,
        "retr_tokenizer": retr_tokenizer,
        "rare_prompt": rare_prompt,
        "orphanet_data": orphanet_data,
        "concept2id": concept2id,
        "orpha2omim": orpha2omim,
        "embeds_disease": embeds_disease,
        "similar_cases": similar_cases,
    }
    return _diagnosis_resources


async def _emit_step(step: str, status: str = "running", detail: str = "", data: dict = None) -> dict:
    """Return an SSE-compatible dict (sse_starlette serialises it automatically)."""
    event = {"step": step, "status": status, "detail": detail}
    if data:
        event["data"] = data
    return {"data": json.dumps(event, ensure_ascii=False)}


async def run_diagnosis_stream(
    clinical_text: str,
    phenotypes: list[str],
    phenotype_ids: list[str],
    model: str,
    provider: str,
    api_key: str | None,
    openai_api_key: str | None,
    search_engine: str = "duckduckgo",
) -> AsyncGenerator[dict, None]:
    """Run phenotype-based diagnosis, yielding SSE events for each step."""
    try:
        yield await _emit_step("initialization", "running", "Setting up models and handlers...")

        resolved_key = get_api_key(provider, api_key)
        oai_key = get_openai_key(openai_api_key)

        if not resolved_key:
            yield await _emit_step("initialization", "error", f"No API key provided for {provider}")
            return
        if not oai_key:
            yield await _emit_step("initialization", "error", "OpenAI API key is required for embeddings")
            return

        handler = create_handler(provider, model, resolved_key)
        oai_handler = create_openai_handler(oai_key)
        mini_handler = oai_handler.mini_completion
        embedding_handler = oai_handler.get_embedding

        resources = await asyncio.to_thread(_load_diagnosis_resources)

        yield await _emit_step("initialization", "completed", "Models loaded successfully")

        phenotype_str = ", ".join(phenotypes) if phenotypes else ""
        phenotype_id_str = ", ".join(phenotype_ids) if phenotype_ids else ""
        patient_info = clinical_text.strip()
        if not patient_info and phenotype_str:
            patient_info = f"Patient presenting with: {phenotype_str}"
        elif not patient_info:
            patient_info = "Patient with unspecified symptoms"
        if not phenotype_str:
            phenotype_str = patient_info

        yield await _emit_step("diagnosis", "running", "Running AI diagnosis pipeline...")

        from diagnosis import make_diagnosis

        args = _WebArgs(search_engine=search_engine, device=resources["device"])
        Path(args.results_folder, "tmp").mkdir(parents=True, exist_ok=True)

        result = await asyncio.to_thread(
            make_diagnosis,
            args,
            0,
            (patient_info, "", phenotype_str, phenotype_id_str),
            resources["rare_prompt"],
            resources["orphanet_data"],
            resources["concept2id"],
            resources["orpha2omim"],
            resources["similar_cases"],
            resources["embeds_disease"],
            resources["eval_model"],
            resources["eval_tokenizer"],
            resources["retr_model"],
            resources["retr_tokenizer"],
            handler,
            mini_handler,
            embedding_handler,
        )

        yield await _emit_step("diagnosis", "completed", "Diagnosis pipeline finished")

        final_text = result.get("final_diagnois", "")
        diseases = _parse_diseases_from_markdown(final_text)

        final_result = {
            "diseases": diseases,
            "raw_diagnosis": result.get("first_round_result", ""),
            "web_evidence": result.get("web_diagnosis", ""),
            "similar_cases": result.get("similar_cases", []),
            "reflection": result.get("judgements", ""),
            "final_diagnosis": final_text,
        }

        yield await _emit_step("complete", "completed", "Diagnosis complete", data=final_result)

    except Exception as e:
        yield await _emit_step("error", "error", f"Diagnosis failed: {str(e)}\n{traceback.format_exc()}")


async def run_gene_diagnosis_stream(
    clinical_text: str,
    phenotypes: list[str],
    phenotype_ids: list[str],
    model: str,
    provider: str,
    api_key: str | None,
    openai_api_key: str | None,
    vcf_path: str | None,
    search_engine: str = "duckduckgo",
) -> AsyncGenerator[dict, None]:
    """Run gene-aware diagnosis with Exomiser, yielding SSE events."""
    try:
        yield await _emit_step("initialization", "running", "Setting up models and Exomiser...")

        resolved_key = get_api_key(provider, api_key)
        oai_key = get_openai_key(openai_api_key)

        if not resolved_key:
            yield await _emit_step("initialization", "error", f"No API key provided for {provider}")
            return
        if not oai_key:
            yield await _emit_step("initialization", "error", "OpenAI API key is required for embeddings")
            return

        handler = create_handler(provider, model, resolved_key)
        oai_handler = create_openai_handler(oai_key)
        mini_handler = oai_handler.mini_completion
        embedding_handler = oai_handler.get_embedding

        resources = await asyncio.to_thread(_load_diagnosis_resources)

        yield await _emit_step("initialization", "completed", "Models loaded")

        phenotype_str = ", ".join(phenotypes) if phenotypes else ""
        phenotype_id_str = ", ".join(phenotype_ids) if phenotype_ids else ""
        patient_info = clinical_text.strip()
        if not patient_info and phenotype_str:
            patient_info = f"Patient presenting with: {phenotype_str}"
        elif not patient_info:
            patient_info = "Patient with unspecified symptoms"
        if not phenotype_str:
            phenotype_str = patient_info
        patient_tuple = (patient_info, "", phenotype_str, phenotype_id_str, vcf_path or "")

        yield await _emit_step("diagnosis", "running", "Running gene-aware diagnosis pipeline...")

        from diagnosisGene import make_diagnosis as make_gene_diagnosis

        args = _WebArgs(
            search_engine=search_engine,
            device=resources["device"],
            exomiser_jar=settings.exomiser_jar_path,
            exomiser_save_path=settings.exomiser_save_path,
        )
        Path(args.results_folder, "tmp").mkdir(parents=True, exist_ok=True)

        result = await asyncio.to_thread(
            make_gene_diagnosis,
            args,
            0,
            patient_tuple,
            resources["rare_prompt"],
            resources["orphanet_data"],
            resources["concept2id"],
            resources["orpha2omim"],
            resources["similar_cases"],
            resources["embeds_disease"],
            resources["eval_model"],
            resources["eval_tokenizer"],
            resources["retr_model"],
            resources["retr_tokenizer"],
            handler,
            mini_handler,
            embedding_handler,
        )

        yield await _emit_step("diagnosis", "completed", "Gene-aware diagnosis finished")

        final_text = result.get("final_diagnois", "")
        diseases = _parse_diseases_from_markdown(final_text)

        final_result = {
            "diseases": diseases,
            "raw_diagnosis": result.get("first_round_result", ""),
            "web_evidence": result.get("web_diagnosis", ""),
            "similar_cases": result.get("similar_cases", []),
            "reflection": result.get("judgements", ""),
            "final_diagnosis": final_text,
            "mutation_details": result.get("mutation_details", ""),
            "variant_data": result.get("variant_data", []),
        }

        yield await _emit_step("complete", "completed", "Gene-aware diagnosis complete", data=final_result)

    except Exception as e:
        yield await _emit_step("error", "error", f"Gene diagnosis failed: {str(e)}\n{traceback.format_exc()}")
