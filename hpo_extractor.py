#!/usr/bin/env python3
"""
HPO Phenotype Extraction and Mapping Pipeline

This script processes patient discharge notes to extract phenotypes using OpenAI API
and maps them to Human Phenotype Ontology (HPO) terms using semantic similarity.
"""
import pandas as pd
import json
import torch
from transformers import AutoTokenizer, AutoModel
import argparse
from typing import List, Dict, Any, Tuple, Optional
from api.interface import Openai_api

def read_csv_file(file_path: str) -> Optional[pd.DataFrame]:
    """
    Read CSV file and return DataFrame
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        DataFrame containing the CSV data or None if error occurs
    """
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        print(f"Error: The file {file_path} does not exist.")
        return None
    except pd.errors.EmptyDataError:
        print("Error: The file is empty.")
        return None
    except pd.errors.ParserError:
        print("Error: There was a parsing error with the file.")
        return None


def get_device() -> torch.device:
    """Get available device (CUDA or CPU)"""
    if torch.cuda.is_available():
        return torch.device('cuda')
    else:
        return torch.device('cpu')


def load_hpo_resources(model_path: str, concept2id_path: str, 
                      concept_embeddings_path: str) -> Tuple[Any, Any, Dict, torch.Tensor, List[str]]:
    """
    Load all HPO mapping resources
    
    Args:
        model_path: Path to biolord model
        concept2id_path: Path to concept2id dictionary file
        concept_embeddings_path: Path to concept embeddings file
    
    Returns:
        Tuple of (model, tokenizer, concept2id, concept_embeddings, concept_keys)
    """
    print("Loading HPO mapping resources...")
    
    # Load model and tokenizer
    print("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModel.from_pretrained(model_path)
    
    # Load concept2id
    print("Loading concept2id...")
    with open(concept2id_path, 'r') as f:
        concept2id = json.load(f)
    
    # Load concept embeddings
    print("Loading concept embeddings...")
    concept_embeddings = torch.load(concept_embeddings_path, map_location='cpu')
    
    # Get concept keys
    concept_keys = list(concept2id.keys())
    
    print("All resources loaded successfully!")
    return model, tokenizer, concept2id, concept_embeddings, concept_keys


def topk_similarity(query_embeddings: torch.Tensor, concept_embeddings: torch.Tensor, 
                   k: int = 1) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Calculate top-k similarity between query and concept embeddings
    
    Args:
        query_embeddings: Query embeddings
        concept_embeddings: Concept embeddings
        k: Number of top results to return
        
    Returns:
        Tuple of (top_k_indices, top_k_values)
    """
    # Normalize embeddings
    query_embeddings = torch.nn.functional.normalize(query_embeddings, p=2, dim=1)
    concept_embeddings = torch.nn.functional.normalize(concept_embeddings, p=2, dim=1)
    
    # Calculate similarity
    similarities = torch.matmul(query_embeddings, concept_embeddings.T)
    
    # Get top-k
    topk_values, topk_indices = torch.topk(similarities, k, dim=1)
    
    return topk_indices, topk_values


def map_phenotypes_to_hpo(phenotypes: List[str], eval_model: Any, eval_tokenizer: Any, 
                         concept2id: Dict, concept_embeddings: torch.Tensor, 
                         concept_keys: List[str], similarity_threshold: float = 0.8) -> List[Dict]:
    """
    Map extracted phenotypes to HPO codes using semantic similarity
    
    Args:
        phenotypes: List of phenotype descriptions
        eval_model: BioLORD model
        eval_tokenizer: Tokenizer
        concept2id: Concept to ID mapping
        concept_embeddings: Concept embeddings
        concept_keys: Concept keys
        similarity_threshold: Similarity threshold for mapping
    
    Returns:
        List of mapping results
    """
    if not phenotypes:
        return []
    
    device = get_device()
    
    # Ensure all components are on the same device
    try:
        eval_model = eval_model.to(device)
        concept_embeddings = concept_embeddings.to(device)
    except Exception as e:
        print(f"Failed to move to {device}: {e}")
        device = torch.device('cpu')
        eval_model = eval_model.to(device)
        concept_embeddings = concept_embeddings.to(device)
        print("Switched to CPU")
    
    # Batch encode phenotype descriptions
    phenotype_embeddings_list = []
    batch_size = 30
    
    for i in range(0, len(phenotypes), batch_size):
        batch_phenotypes = phenotypes[i:i+batch_size]
        
        try:
            inputs = eval_tokenizer(batch_phenotypes, 
                                   padding=True, 
                                   truncation=True, 
                                   max_length=128, 
                                   return_tensors="pt").to(device)
            
            with torch.no_grad():
                outputs = eval_model(**inputs)
            
            phenotype_embeddings_list.append(outputs.last_hidden_state[:,0,:])
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower() and device.type == 'cuda':
                print("GPU OOM, switching to CPU")
                torch.cuda.empty_cache()
                
                # Move all components to CPU
                device = torch.device('cpu')
                eval_model = eval_model.to(device)
                concept_embeddings = concept_embeddings.to(device)
                
                # Move existing embeddings to CPU
                phenotype_embeddings_list = [emb.to(device) for emb in phenotype_embeddings_list]
                
                # Reprocess current batch
                inputs = eval_tokenizer(batch_phenotypes, 
                                       padding=True, 
                                       truncation=True, 
                                       max_length=128, 
                                       return_tensors="pt").to(device)
                
                with torch.no_grad():
                    outputs = eval_model(**inputs)
                
                phenotype_embeddings_list.append(outputs.last_hidden_state[:,0,:])
            else:
                raise e
    
    # Concatenate all embeddings
    phenotype_embeddings = torch.cat(phenotype_embeddings_list, 0)
    
    # Calculate similarity and get best matches
    topk_indices, topk_values = topk_similarity(phenotype_embeddings, concept_embeddings, k=1)
    
    # Convert to CPU numpy arrays
    topk_indices = topk_indices.cpu().numpy().tolist()
    topk_values = topk_values.cpu().numpy().tolist()
    
    concept_values = list(concept2id.values())
    
    mapped_results = []
    seen_hpo_codes = set()
    
    for i, phenotype in enumerate(phenotypes):
        best_match_idx = topk_indices[i][0]
        similarity_score = topk_values[i][0]
        
        if similarity_score < similarity_threshold:
            print(f"Dropping phenotype '{phenotype}' due to low similarity score: {similarity_score:.3f}")
            mapped_results.append({
                'original_phenotype': phenotype,
                'hpo_code': None,
                'hpo_term': None,
                'similarity_score': similarity_score,
                'status': 'low_similarity'
            })
            continue
        
        mapped_hpo_code = concept_values[best_match_idx]
        mapped_concept_name = concept_keys[best_match_idx]
        
        # Check for duplicates
        if mapped_hpo_code in seen_hpo_codes:
            print(f"Duplicate HPO code '{mapped_hpo_code}' found, skipping phenotype '{phenotype}'")
            mapped_results.append({
                'original_phenotype': phenotype,
                'hpo_code': mapped_hpo_code,
                'hpo_term': mapped_concept_name,
                'similarity_score': similarity_score,
                'status': 'duplicate'
            })
            continue
        
        seen_hpo_codes.add(mapped_hpo_code)
        print(f"Mapping phenotype '{phenotype}' to HPO code '{mapped_hpo_code}' with similarity score {similarity_score:.3f}")
        
        mapped_results.append({
            'original_phenotype': phenotype,
            'hpo_code': mapped_hpo_code,
            'hpo_term': mapped_concept_name,
            'similarity_score': similarity_score,
            'status': 'mapped'
        })
    
    return mapped_results


def extract_phenotypes_from_text(text: str, api: Openai_api) -> List[str]:
    """
    Extract phenotypes from patient text using OpenAI API
    
    Args:
        text: Patient information text
        api: OpenAI API client
        
    Returns:
        List of extracted phenotypes
    """
    system_prompt = "You are a medical expert specialized in rare disease and phenotype extraction."
    
    prompt = (f"Given a paragraph of patient information from discharge note, please extract the phenotype about this patient only. "
             f"Check the Human Phenotype Ontology (HPO) database to determine the phenotype. "
             f"Only output the extracted phenotypes. "
             f"Use the format: {{'HPO': 'HP:0000000', 'Phenotype': 'Phenotype description'}} "
             f"Use \\n as the separator between different phenotypes. "
             f"Please describe in English. "
             f"Do not output any other information. "
             f"Patient information: {text}")
    
    response = api.get_completion(system_prompt, prompt)
    
    if response is None:
        return []
    
    # Parse API response to extract phenotypes
    response_lines = response.split('\n')
    response_lines = [line.strip() for line in response_lines if line.strip()]
    response_lines = [line for line in response_lines if line.startswith("{") and line.endswith("}")]
    
    extracted_phenotypes = []
    for item in response_lines:
        try:
            phenotype_data = eval(item)
            if 'HPO' in phenotype_data and 'Phenotype' in phenotype_data:
                extracted_phenotypes.append(phenotype_data['Phenotype'])
        except:
            print(f"Failed to parse: {item}")
            continue
    
    return extracted_phenotypes


def process_phenotype_list(phenotype_list: List[str], api_key: str, hpo_model: Any, 
                          hpo_tokenizer: Any, concept2id: Dict, concept_embeddings: torch.Tensor, 
                          concept_keys: List[str], model: str = 'gpt-4.1', 
                          similarity_threshold: float = 0.8) -> List[Dict]:
    """
    Process phenotype description list, extract phenotypes and map to HPO terms
    
    Args:
        phenotype_list: List of patient information texts
        api_key: OpenAI API key
        hpo_model: HPO mapping model
        hpo_tokenizer: HPO mapping tokenizer
        concept2id: Concept to ID mapping
        concept_embeddings: Concept embeddings
        concept_keys: Concept keys
        model: Model name to use
        similarity_threshold: HPO mapping similarity threshold
    
    Returns:
        List of processing results
    """
    # Initialize API
    api = Openai_api(api_key, model)
    
    results = []
    
    # Process each case
    for i, phenotype_text in enumerate(phenotype_list):
        print(f"Processing case {i+1}/{len(phenotype_list)}")
        
        # Extract phenotypes using API
        extracted_phenotypes = extract_phenotypes_from_text(str(phenotype_text), api)
        
        print(f"Extracted {len(extracted_phenotypes)} phenotypes")
        
        # Map extracted phenotypes to HPO
        if extracted_phenotypes:
            hpo_mappings = map_phenotypes_to_hpo(
                extracted_phenotypes, 
                hpo_model, 
                hpo_tokenizer,
                concept2id, 
                concept_embeddings, 
                concept_keys,
                similarity_threshold
            )
        else:
            hpo_mappings = []
        
        results.append({
            'original_text': phenotype_text,
            'extracted_phenotypes': extracted_phenotypes,
            'hpo_mappings': hpo_mappings,
            'status': 'success'
        })
        
        mapped_count = len([m for m in hpo_mappings if m['status'] == 'mapped'])
        print(f"Successfully mapped {mapped_count} HPO terms")
        print("-" * 80)
    
    return results


def map_hpo_to_phenotype(hpo_id: str, id2concept: Dict) -> str:
    """
    Map HPO ID to phenotype description
    
    Args:
        hpo_id: HPO ID string
        id2concept: ID to concept mapping dictionary
    
    Returns:
        Phenotype description string
    """
    return id2concept.get(hpo_id, "Unknown Phenotype")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='HPO Phenotype Extraction and Mapping Pipeline')
    parser.add_argument('--input_csv', required=True, help='Path to input CSV file')
    parser.add_argument('--output_csv', required=True, help='Path to output CSV file')
    parser.add_argument('--text_column', default='信息', help='Column name containing patient information')
    parser.add_argument('--api_key', required=True, help='OpenAI API key')
    parser.add_argument('--model_path', default='FremyCompany/BioLORD-2023-C', help='Path to BioLORD model')
    parser.add_argument('--concept2id_path', required=True, help='Path to concept2id JSON file')
    parser.add_argument('--concept_embeddings_path', required=True, help='Path to concept embeddings file')
    parser.add_argument('--phenotype_mapping_path', required=True, help='Path to phenotype mapping JSON file')
    parser.add_argument('--model_name', default='gpt-4.1', help='OpenAI model name')
    parser.add_argument('--similarity_threshold', type=float, default=0.8, help='HPO mapping similarity threshold')
    
    args = parser.parse_args()
    
    # Read input CSV
    print(f"Reading input CSV: {args.input_csv}")
    df = read_csv_file(args.input_csv)
    if df is None:
        return
    
    # Load HPO mapping resources
    print("Loading HPO mapping resources...")
    hpo_model, hpo_tokenizer, concept2id, concept_embeddings, concept_keys = load_hpo_resources(
        args.model_path, args.concept2id_path, args.concept_embeddings_path
    )
    
    # Get phenotype list from DataFrame
    phenotype_list = list(df[args.text_column])
    
    # Process phenotype list
    print("Starting phenotype extraction and mapping...")
    results = process_phenotype_list(
        phenotype_list, 
        args.api_key, 
        hpo_model, 
        hpo_tokenizer,
        concept2id, 
        concept_embeddings, 
        concept_keys,
        model=args.model_name,
        similarity_threshold=args.similarity_threshold
    )
    
    # Load phenotype mapping for HPO descriptions
    print(f"Loading phenotype mapping: {args.phenotype_mapping_path}")
    with open(args.phenotype_mapping_path, 'r') as f:
        id2concept = json.load(f)
    
    # Add results to DataFrame
    df['phenotype_extraction_results'] = results
    df['hpo_codes'] = [
        [m['hpo_code'] for m in result['hpo_mappings'] if m['status'] == 'mapped'] 
        for result in results
    ]
    df['hpo_descriptions'] = df['hpo_codes'].apply(
        lambda codes: [map_hpo_to_phenotype(code, id2concept) for code in codes if code in id2concept]
    )
    
    # Save results
    print(f"Saving results to: {args.output_csv}")
    df.to_csv(args.output_csv, index=False)
    
    # Print summary
    print("\n=== Processing Summary ===")
    total_cases = len(results)
    successful_cases = len([r for r in results if r['status'] == 'success'])
    total_mapped_hpo = sum(len([m for m in r['hpo_mappings'] if m['status'] == 'mapped']) for r in results)
    
    print(f"Total cases processed: {total_cases}")
    print(f"Successful cases: {successful_cases}")
    print(f"Total HPO terms mapped: {total_mapped_hpo}")
    print(f"Average HPO terms per case: {total_mapped_hpo/total_cases:.2f}")


if __name__ == "__main__":
    main()