#!/bin/bash
# HPO Phenotype Extraction and Mapping Pipeline
# This script runs the HPO extraction pipeline with specified parameters

INPUT_CSV="./dataset/cases.csv"
OUTPUT_CSV="processed_cases.csv"
TEXT_COLUMN="description"
API_KEY=""
MODEL_PATH="FremyCompany/BioLORD-2023-C"
CONCEPT2ID_PATH="./database/definition2id.json"
CONCEPT_EMBEDDINGS_PATH="./database/embeds_pheno.pt"
PHENOTYPE_MAPPING_PATH="./database/phenotype_mapping.json"
MODEL_NAME="gpt-4.1"
SIMILARITY_THRESHOLD=0.8

# Run the Python script
python hpo_extractor.py \
    --input_csv "$INPUT_CSV" \
    --output_csv "$OUTPUT_CSV" \
    --text_column "$TEXT_COLUMN" \
    --api_key "$API_KEY" \
    --model_path "$MODEL_PATH" \
    --concept2id_path "$CONCEPT2ID_PATH" \
    --concept_embeddings_path "$CONCEPT_EMBEDDINGS_PATH" \
    --phenotype_mapping_path "$PHENOTYPE_MAPPING_PATH" \
    --model_name "$MODEL_NAME" \
    --similarity_threshold "$SIMILARITY_THRESHOLD" \