"""
VEP API-based variant analysis - lightweight replacement for Exomiser.
Uses Ensembl VEP REST API (free, no API key) to annotate VCF variants
with consequence, SIFT, PolyPhen, and population frequencies.
"""
import os
import re
import json
import time
import requests
from pathlib import Path

VEP_REST = "https://grch37.rest.ensembl.org"
BATCH_SIZE = 150
MAX_RETRIES = 3
RETRY_DELAY = 5

NON_CODING_CONSEQUENCES = {
    "5_prime_UTR_variant", "3_prime_UTR_variant",
    "non_coding_transcript_exon_variant", "non_coding_transcript_variant",
    "intron_variant", "upstream_gene_variant", "downstream_gene_variant",
    "intergenic_variant", "regulatory_region_variant", "TF_binding_site_variant",
    "non_coding_transcript_intron_variant",
}

SEVERITY_ORDER = [
    "transcript_ablation", "splice_acceptor_variant", "splice_donor_variant",
    "stop_gained", "frameshift_variant", "stop_lost", "start_lost",
    "transcript_amplification", "inframe_insertion", "inframe_deletion",
    "missense_variant", "protein_altering_variant", "splice_region_variant",
    "incomplete_terminal_codon_variant", "start_retained_variant",
    "stop_retained_variant", "synonymous_variant",
]


def parse_vcf(vcf_path, quality_filter=True):
    """Parse VCF and return list of variant dicts, deduplicating by position."""
    variants = []
    seen = set()

    with open(vcf_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, vid, ref, alt, qual, filt = parts[0:7]

            if quality_filter and filt not in ("PASS", "."):
                continue

            chrom_clean = chrom.replace("chr", "")
            if chrom_clean not in [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]:
                continue

            for a in alt.split(","):
                key = f"{chrom_clean}:{pos}:{ref}:{a}"
                if key in seen:
                    continue
                seen.add(key)

                gt = ""
                if len(parts) > 9:
                    fmt = parts[8].split(":")
                    sample = parts[9].split(":")
                    gt_idx = fmt.index("GT") if "GT" in fmt else -1
                    if gt_idx >= 0 and gt_idx < len(sample):
                        gt = sample[gt_idx]

                variants.append({
                    "chrom": chrom_clean,
                    "pos": int(pos),
                    "ref": ref,
                    "alt": a,
                    "id": vid,
                    "qual": qual,
                    "filter": filt,
                    "genotype": gt,
                })

    return variants


def _vep_region_str(v):
    """Build VEP region string for a variant."""
    chrom, pos, ref, alt = v["chrom"], v["pos"], v["ref"], v["alt"]

    if len(ref) == 1 and len(alt) == 1:
        return f"{chrom} {pos} {pos} {ref}/{alt} 1"
    elif len(ref) > len(alt):
        start = pos + 1
        end = pos + len(ref) - len(alt)
        deleted = ref[1:] if len(alt) == 1 else ref[len(alt):]
        return f"{chrom} {start} {end} {deleted}/- 1"
    else:
        start = pos + 1
        end = pos
        inserted = alt[1:] if len(ref) == 1 else alt[len(ref):]
        return f"{chrom} {start} {end} -/{inserted} 1"


def annotate_with_vep(variants, progress_callback=None):
    """Send variants to Ensembl VEP REST API in batches."""
    all_annotations = []
    total = len(variants)

    for i in range(0, total, BATCH_SIZE):
        batch = variants[i:i + BATCH_SIZE]
        regions = [_vep_region_str(v) for v in batch]

        payload = {"variants": regions}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(
                    f"{VEP_REST}/vep/homo_sapiens/region",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", RETRY_DELAY))
                    print(f"VEP rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"VEP request failed (attempt {attempt + 1}): {e}")
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    print(f"VEP request failed after {MAX_RETRIES} attempts: {e}")
                    data = []

        for j, ann in enumerate(data if isinstance(data, list) else []):
            idx = i + j
            if idx < len(variants):
                variants[idx]["vep"] = ann

        processed = min(i + BATCH_SIZE, total)
        if progress_callback:
            progress_callback(processed, total)
        else:
            print(f"VEP annotation: {processed}/{total} variants")

        if i + BATCH_SIZE < total:
            time.sleep(1)

    return variants


def _extract_best_transcript(vep_ann):
    """Pick the most severe transcript consequence from VEP annotation."""
    tcs = vep_ann.get("transcript_consequences", [])
    if not tcs:
        return None

    def severity(tc):
        terms = tc.get("consequence_terms", [])
        best = len(SEVERITY_ORDER)
        for t in terms:
            if t in SEVERITY_ORDER:
                best = min(best, SEVERITY_ORDER.index(t))
        return best

    tcs_sorted = sorted(tcs, key=severity)
    return tcs_sorted[0]


def _get_max_pop_freq(vep_ann):
    """Get the maximum population allele frequency from colocated variants."""
    max_freq = 0.0
    for coloc in vep_ann.get("colocated_variants", []):
        freqs = coloc.get("frequencies", {})
        for allele_freqs in freqs.values():
            if isinstance(allele_freqs, dict):
                for f in allele_freqs.values():
                    if isinstance(f, (int, float)):
                        max_freq = max(max_freq, f)
            elif isinstance(allele_freqs, (int, float)):
                max_freq = max(max_freq, allele_freqs)

        if coloc.get("minor_allele_freq"):
            max_freq = max(max_freq, coloc["minor_allele_freq"])

    return max_freq


def filter_and_rank(variants, max_freq=0.01):
    """Filter variants by frequency and pathogenicity, then rank by severity."""
    candidates = []

    for v in variants:
        vep = v.get("vep")
        if not vep:
            continue

        tc = _extract_best_transcript(vep)
        if not tc:
            continue

        consequences = tc.get("consequence_terms", [])
        if all(c in NON_CODING_CONSEQUENCES for c in consequences):
            continue

        pop_freq = _get_max_pop_freq(vep)
        if pop_freq > max_freq:
            continue

        sift = tc.get("sift_prediction", "")
        sift_score = tc.get("sift_score")
        polyphen = tc.get("polyphen_prediction", "")
        polyphen_score = tc.get("polyphen_score")
        gene = tc.get("gene_symbol", "")
        gene_id = tc.get("gene_id", "")
        hgvsc = tc.get("hgvsc", "")
        hgvsp = tc.get("hgvsp", "")
        impact = tc.get("impact", "")
        biotype = tc.get("biotype", "")

        clinvar_sig = ""
        clinvar_id = ""
        for coloc in vep.get("colocated_variants", []):
            cs = coloc.get("clin_sig", [])
            if cs:
                clinvar_sig = ", ".join(cs) if isinstance(cs, list) else str(cs)
            if coloc.get("var_synonyms", {}).get("ClinVar"):
                clinvar_id = str(coloc["var_synonyms"]["ClinVar"])

        pathogenicity_score = 0.0
        if "deleterious" in sift:
            pathogenicity_score += 0.3
        if "damaging" in polyphen:
            pathogenicity_score += 0.3
        if polyphen == "probably_damaging":
            pathogenicity_score += 0.1
        if "pathogenic" in clinvar_sig.lower():
            pathogenicity_score += 0.5
        if impact == "HIGH":
            pathogenicity_score += 0.4
        elif impact == "MODERATE":
            pathogenicity_score += 0.2
        if pop_freq == 0:
            pathogenicity_score += 0.1

        severity_idx = len(SEVERITY_ORDER)
        for c in consequences:
            if c in SEVERITY_ORDER:
                severity_idx = min(severity_idx, SEVERITY_ORDER.index(c))

        candidates.append({
            "gene": gene,
            "gene_id": gene_id,
            "chrom": v["chrom"],
            "pos": v["pos"],
            "ref": v["ref"],
            "alt": v["alt"],
            "rsid": v.get("id", ""),
            "genotype": v.get("genotype", ""),
            "consequence": ", ".join(consequences),
            "impact": impact,
            "hgvsc": hgvsc,
            "hgvsp": hgvsp,
            "sift": f"{sift} ({sift_score})" if sift_score is not None else sift,
            "polyphen": f"{polyphen} ({polyphen_score})" if polyphen_score is not None else polyphen,
            "pop_freq": pop_freq,
            "clinvar": clinvar_sig,
            "pathogenicity_score": round(pathogenicity_score, 2),
            "severity_rank": severity_idx,
            "biotype": biotype,
        })

    candidates.sort(key=lambda x: (-x["pathogenicity_score"], x["severity_rank"], x["pop_freq"]))
    return candidates


def build_summary(ranked_variants, max_genes=20):
    """Build a text summary mimicking Exomiser output format."""
    if not ranked_variants:
        return "No potentially pathogenic variants found in the VCF."

    seen_genes = {}
    for v in ranked_variants:
        gene = v["gene"]
        if not gene or gene in seen_genes:
            if gene in seen_genes:
                seen_genes[gene]["variants"].append(v)
            continue
        seen_genes[gene] = {"top_variant": v, "variants": [v]}

    gene_list = sorted(
        seen_genes.values(),
        key=lambda g: (-g["top_variant"]["pathogenicity_score"], g["top_variant"]["severity_rank"]),
    )[:max_genes]

    lines = []
    for entry in gene_list:
        tv = entry["top_variant"]
        lines.append(
            f"Gene: {tv['gene']} (chr{tv['chrom']})\n"
            f"  Pathogenicity score: {tv['pathogenicity_score']}, Impact: {tv['impact']}\n"
            f"  Top variant: {tv['chrom']}:{tv['pos']} {tv['ref']}>{tv['alt']} ({tv['genotype']})\n"
            f"  Consequence: {tv['consequence']}\n"
            f"  HGVS: {tv['hgvsc']} / {tv['hgvsp']}\n"
            f"  SIFT: {tv['sift']} | PolyPhen: {tv['polyphen']}\n"
            f"  Population freq: {tv['pop_freq']:.6f} | ClinVar: {tv['clinvar'] or 'N/A'}"
        )
        if len(entry["variants"]) > 1:
            lines.append(f"  Additional variants in gene: {len(entry['variants']) - 1}")
        lines.append("")

    return "\n".join(lines).strip()


def build_diagnosis_prompt(summary, patient_info, preliminary_diagnosis):
    """Build LLM prompt for gene-aware diagnosis."""
    return (
        "Here is a rare disease diagnosis case.\n\n"
        "VEP-based gene/variant prioritization summary:\n"
        f"{summary}\n\n"
        f"Phenotypic description: {patient_info}\n\n"
        f"Preliminary diagnosis based only on phenotype: {preliminary_diagnosis}\n\n"
        "Based on all the above, enumerate the top 5 most likely rare disease diagnoses.\n\n"
        "---\n\n"
        "**For each diagnosis, follow this format exactly:**\n\n"
        "## **DISEASE NAME** (Rank #X/5)\n\n"
        "### Diagnostic Reasoning:\n"
        "- Provide 3-4 sentences explaining why this diagnosis fits the patient's presentation.\n"
        "- Specify which patient symptoms and findings support this diagnosis.\n"
        "- Explain which gene variants from the VEP analysis support this diagnosis and why.\n"
        "- Clearly explain the underlying pathophysiological mechanisms (briefly).\n\n"
        "---\n\n"
        "Please consider the gene results from variant analysis carefully - "
        "if a known disease gene has a rare, damaging variant that matches the phenotype, "
        "it should be ranked highly."
    )


def run_vep_diagnosis(vcf_path, hpo_ids, patient_info="",
                      preliminary_diagnosis="", api_interface=None,
                      progress_callback=None):
    """
    Full pipeline: parse VCF -> VEP annotation -> filter -> rank -> LLM diagnosis.
    Drop-in replacement for ExomiserRunner.run_diagnosis_inference.
    """
    sample_id = Path(vcf_path).stem.replace(".vcf", "")
    print(f"[VEP Analysis] Starting analysis for {sample_id}")

    print(f"[VEP Analysis] Step 1: Parsing VCF...")
    variants = parse_vcf(vcf_path)
    print(f"[VEP Analysis] Found {len(variants)} PASS variants")

    if not variants:
        return {
            "sample_id": sample_id,
            "ai_diagnosis": "No PASS variants found in VCF file.",
            "vep_summary": "No variants to analyze.",
        }

    print(f"[VEP Analysis] Step 2: Annotating with Ensembl VEP API...")
    variants = annotate_with_vep(variants, progress_callback)

    print(f"[VEP Analysis] Step 3: Filtering and ranking variants...")
    ranked = filter_and_rank(variants, max_freq=0.01)
    print(f"[VEP Analysis] {len(ranked)} candidate variants after filtering")

    print(f"[VEP Analysis] Step 4: Building summary...")
    summary = build_summary(ranked, max_genes=20)

    ai_diagnosis = ""
    if api_interface and summary:
        print(f"[VEP Analysis] Step 5: Running AI diagnosis with gene data...")
        prompt = build_diagnosis_prompt(summary, patient_info, preliminary_diagnosis)
        system = "You are an expert in rare disease diagnosis and clinical genetics."
        try:
            ai_diagnosis = api_interface.get_completion(system, prompt)
        except Exception as e:
            print(f"[VEP Analysis] AI diagnosis failed: {e}")
            ai_diagnosis = f"AI diagnosis unavailable: {e}"
    else:
        ai_diagnosis = preliminary_diagnosis

    return {
        "sample_id": sample_id,
        "vcf_path": vcf_path,
        "hpo_ids": hpo_ids,
        "patient_info": patient_info,
        "preliminary_diagnosis": preliminary_diagnosis,
        "vep_summary": summary,
        "n_total_variants": len(variants),
        "n_candidate_variants": len(ranked),
        "top_candidates": ranked[:20],
        "ai_diagnosis": ai_diagnosis,
    }
