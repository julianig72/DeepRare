"""HPO extraction service - wraps hpo_extractor.py logic for web use."""
import sys
from pathlib import Path
from app.config import DEEPRARE_ROOT, settings
from app.services.model_manager import create_openai_handler, get_openai_key

if str(DEEPRARE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEEPRARE_ROOT))

_hpo_resources = None


def _get_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_hpo_resources():
    """Load BioLORD model and HPO concept embeddings (cached singleton)."""
    global _hpo_resources
    if _hpo_resources is not None:
        return _hpo_resources

    import torch
    from transformers import AutoTokenizer, AutoModel

    device = _get_device()
    model_name = "FremyCompany/BioLORD-2023-C"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)

    concept2id_path = settings.hpo_concept2id_path
    embeddings_path = settings.hpo_embeddings_path

    concept2id = {}
    concept_embeddings = None

    if concept2id_path and Path(concept2id_path).exists():
        import json
        with open(concept2id_path, "r") as f:
            concept2id = json.load(f)

    if embeddings_path and Path(embeddings_path).exists():
        concept_embeddings = torch.load(embeddings_path, map_location=device)

    _hpo_resources = {
        "tokenizer": tokenizer,
        "model": model,
        "device": device,
        "concept2id": concept2id,
        "concept_embeddings": concept_embeddings,
    }
    return _hpo_resources


def _embed_texts(texts: list[str], tokenizer, model, device):
    """Get BioLORD embeddings for a list of texts."""
    import torch
    encoded = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)
    with torch.no_grad():
        output = model(**encoded)
    embeddings = output.last_hidden_state[:, 0, :]
    return embeddings / embeddings.norm(dim=1, keepdim=True)


def _topk_similarity(query_emb, corpus_emb, k: int = 5):
    """Return top-k most similar indices and scores."""
    import torch
    sim = torch.mm(query_emb, corpus_emb.T)
    scores, indices = torch.topk(sim, k=min(k, corpus_emb.size(0)), dim=1)
    return scores[0].cpu().tolist(), indices[0].cpu().tolist()


async def extract_hpo_from_text(clinical_text: str, openai_api_key: str | None = None) -> dict:
    """Extract phenotypes from clinical text and map to HPO terms."""
    api_key = get_openai_key(openai_api_key)
    if not api_key:
        raise ValueError("OpenAI API key is required for HPO extraction")

    handler = create_openai_handler(api_key)

    system_prompt = (
        "You are a medical expert specializing in rare diseases. "
        "Extract all phenotype descriptions from the clinical text. "
        "Return ONLY a Python list of strings, each being a distinct phenotype. "
        "Example: [\"seizures\", \"intellectual disability\", \"microcephaly\"]"
    )

    raw_response = handler.get_completion(system_prompt, clinical_text)

    try:
        import ast
        phenotype_list = ast.literal_eval(raw_response.strip())
        if not isinstance(phenotype_list, list):
            phenotype_list = [raw_response.strip()]
    except Exception:
        lines = [l.strip().strip("-•*").strip() for l in raw_response.strip().split("\n") if l.strip()]
        phenotype_list = [l for l in lines if len(l) > 2]

    resources = load_hpo_resources()
    results = []

    if resources["concept_embeddings"] is not None and resources["concept2id"]:
        id2concept = {v: k for k, v in resources["concept2id"].items()}
        query_embs = _embed_texts(phenotype_list, resources["tokenizer"], resources["model"], resources["device"])

        for i, phenotype in enumerate(phenotype_list):
            scores, indices = _topk_similarity(query_embs[i:i+1], resources["concept_embeddings"], k=1)
            if indices:
                hpo_code = id2concept.get(indices[0], "Unknown")
                concept_name = resources["concept2id"].get(hpo_code, hpo_code)
                results.append({
                    "phenotype_text": phenotype,
                    "hpo_code": hpo_code,
                    "hpo_description": concept_name if isinstance(concept_name, str) else hpo_code,
                    "similarity": round(scores[0], 4),
                })
            else:
                results.append({
                    "phenotype_text": phenotype,
                    "hpo_code": "",
                    "hpo_description": "",
                    "similarity": 0.0,
                })
    else:
        for phenotype in phenotype_list:
            results.append({
                "phenotype_text": phenotype,
                "hpo_code": "",
                "hpo_description": "HPO embeddings not loaded",
                "similarity": 0.0,
            })

    return {
        "phenotypes": results,
        "raw_extraction": raw_response,
    }
