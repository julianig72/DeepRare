import os
import argparse
import json
import torch
import torch.nn.functional as F
import pandas as pd
import numpy as np

from data import RareDataset, RarePrompt
from tqdm import tqdm

def set_up_args():
    
    print("Setting up the arguments...")
    
    parser = argparse.ArgumentParser()
    # model 
    parser.add_argument('--model', type=str, default="openai", choices=["openai", "gemini", "deepseek", "claude"])

    # chrome driver path
    parser.add_argument('--chrome_driver', type=str, default='/usr/local/bin/chromedriver')
    
    # file paths
    parser.add_argument('--orphanetPath', type=str, default='./database/orpha_disorders_HP_map.json')
    parser.add_argument('--orpha_concept2id', type=str, default='./database/orpha_concept2id.json')
    parser.add_argument('--orpha_checkpoints', type=str, default='./database/embeds_concept.pt') # not necessary
    parser.add_argument('--phenotype_mapping', type=str, default='./database/phenotype_mapping.json')
    parser.add_argument('--disease_mapping', type=str, default='./database/disease_mapping.json')
    parser.add_argument('--orpha_omim', type=str, default='./database/orpha2omim.json')
    parser.add_argument('--orpha_name', type=str, default='./database/orpha2name.json')
    parser.add_argument('--bert_model', type=str, default='FremyCompany/BioLORD-2023-C')
    parser.add_argument('--retrieval_model', type=str, default='ncbi/MedCPT-Cross-Encoder')
    parser.add_argument('--similar_case_path', type=str, default='./database/RDS_embeddings.csv')
    parser.add_argument('--dataset_name', type=str, default="HMS", choices=["RAMEDIS", "MME", "HMS", "LIRICAL", "Xinhua", "MIMIC", "mygene", "DDD", "case"])
    parser.add_argument('--dataset_path', default='chenxz/RareBench')
    parser.add_argument('--results_folder', default='./result_simcase1/')
    parser.add_argument('--exomiser_jar', type=str, default='./exomiser-cli-14.1.0/exomiser-cli-14.1.0.jar')  # Path to Exomiser JAR file
    parser.add_argument('--exomiser_save_path', type=str, default='exomiser_results/')  # Directory to save Exomiser results
    
    # API keys
    parser.add_argument('--openai_apikey', type=str, default='')
    parser.add_argument('--openai_model', type=str, default='gpt-4o', choices=['gpt-4o', 'gpt-4o-mini', 'o1', 'o3-mini', 'o1-mini'])
    parser.add_argument('--gemini_apikey', type=str, default='')
    parser.add_argument('--gemini_model', type=str, default='', choices=['gemini-2.0-pro-exp', 'gemini-2.0-flash-exp', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash-8b', 'gemini-1.5-flash'])
    parser.add_argument('--claude_apikey', type=str, default='')
    parser.add_argument('--claude_model', type=str, default='', choices=['claude-3-7-sonnet-20250219', 'claude-3-7-sonnet-thinking'])
    parser.add_argument('--deepseek_apikey', type=str, default='') # pip install -U 'volcengine-python-sdk[ark]'
    parser.add_argument('--deepseek_model', type=str, default="deepseek-r1-250120")
    parser.add_argument('--uptodate_pwd', type=str, default='')
    parser.add_argument('--uptodate_user', type=str, default='')
    parser.add_argument('--google_api', type=str, default='')
    parser.add_argument('--search_engine_id', type=str, default='')
    
    # Other arguments
    parser.add_argument('--search_engine', type=str, default='bing', choices=['google', 'bing', 'duckduckgo'])
    parser.add_argument('--visualize', type=bool, default=False) # for visualizing the search results
    parser.add_argument('--screenshots', type=bool, default=False)
    
    # if add gene information to diagnosis
    parser.add_argument('--gene', type=bool, default=False)
    
    args = parser.parse_args()
    
    args.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Set up the results folder
    results_folder = os.path.join(args.results_folder, args.dataset_name)
    if args.model == 'openai':
        results_folder = os.path.join(results_folder, args.openai_model)
    elif args.model == 'gemini':
        results_folder = os.path.join(results_folder, args.gemini_model)
    elif args.model == 'deepseek':
        results_folder = os.path.join(results_folder, args.deepseek_model)
    elif args.model == 'claude':
        results_folder = os.path.join(results_folder, args.claude_model)
        
    os.makedirs(results_folder, exist_ok=True)
    os.makedirs(os.path.join(args.results_folder, 'tmp'), exist_ok=True)
    
    return args, results_folder

def set_up_data(args, eval_model, eval_tokenizer):
    
    print("Setting up the data...")
    
    # Set up the dataset
    dataset = RareDataset(args)
    rare_prompt = RarePrompt()
    
    # ORPHANET Data Base
    with open(args.orphanetPath, "r", encoding="utf-8-sig") as f:
        orphanet_data = json.load(f)
    
    # ORPHANET Concept2ID
    with open(args.orpha_concept2id, "r", encoding="utf-8-sig") as f:
        concept2id = json.load(f)
        
    # ORPHANET OMIM
    with open(args.orpha_omim, "r", encoding="utf-8-sig") as f:
        orpha2omim = json.load(f)
        
    # load similar cases 
    pubmed_cases = pd.read_csv(args.similar_case_path)[['_id', 'case_report', 'embedding', 'diagnosis']]
    pubmed_cases['data_source'] = 'PubMed_cases'

    xinhua_cases = pd.read_csv('dataset/xinhua_rag_0331.csv')
    xinhua_cases = xinhua_cases[['门诊号', 'phenotype', 'embedding', 'orpha']].rename(
        columns={'门诊号': '_id', 'phenotype': 'case_report',  'orpha': 'diagnosis'})
    xinhua_cases['data_source'] = 'xinhua'
    
    def map_disease(disease_mapping, disease_list):
        disease = [disease_mapping[disease] for disease in disease_list if disease in disease_mapping]
        return ', '.join(disease)
        
    disease_mapping = json.load(open(args.disease_mapping, "r", encoding="utf-8-sig"))    
    xinhua_cases['diagnosis'] = xinhua_cases['diagnosis'].apply(lambda x: map_disease(disease_mapping, eval(x)))
    
    mimic_cases = pd.read_csv('dataset/mimic_rag.csv')
    mimic_cases = mimic_cases[['note_id', 'phenotype', 'embedding', 'diagnosis']].rename(
        columns={'note_id': '_id', 'phenotype': 'case_report'})
    mimic_cases['data_source'] = 'mimic'
    
    rarebench_cases = pd.read_csv('dataset/rarebench_rag.csv')
    rarebench_cases = rarebench_cases[['Department', 'Phenotype_detailed', 'embedding', 'Disease_detailed']].rename(
        columns={'Department': '_id', 'Phenotype_detailed': 'case_report', 'Disease_detailed': 'diagnosis'})
    rarebench_cases['data_source'] = 'rarebench'
    
    mygene_cases = pd.read_csv('dataset/mygene_rag.csv')
    mygene_cases = mygene_cases[['rag_id', 'Phenotype_detailed', 'embedding', 'Disease_detailed']].rename(
        columns={'rag_id': '_id', 'Phenotype_detailed': 'case_report', 'Disease_detailed': 'diagnosis'})
    mygene_cases['data_source'] = 'mygene'
    
    ddd_cases = pd.read_csv('dataset/ddd_rag.csv')
    ddd_cases = ddd_cases[['rag_id', 'Phenotype_detailed', 'embedding', 'Disease_detailed']].rename(
        columns={'rag_id': '_id', 'Phenotype_detailed': 'case_report', 'Disease_detailed': 'diagnosis'})
    ddd_cases['data_source'] = 'ddd'

    # Combine the similar cases
    similar_cases = pd.concat([pubmed_cases, xinhua_cases, mimic_cases, rarebench_cases, mygene_cases, ddd_cases], ignore_index=True)
    
    # drop empty embeddings
    similar_cases = similar_cases[similar_cases['embedding'].notna()]
    
    print(f"Loaded {len(similar_cases)} similar cases.")
    
    
    # Get the disease embeddings
    embeds_disease = get_disease_embeddings(args, eval_model, eval_tokenizer, concept2id)
    
    return dataset, rare_prompt, orphanet_data, concept2id, orpha2omim, similar_cases, embeds_disease


def get_disease_embeddings(args, eval_model, eval_tokenizer, concept2id):
    if os.path.exists(args.orpha_checkpoints):
        # Load the embeddings
        embeds_disease = torch.load(args.orpha_checkpoints, map_location='cpu', weights_only=False)
        embeds_disease = torch.tensor(embeds_disease)
        print(f"Loaded embeddings from {args.orpha_checkpoints}")
    else:
        device = args.device
        query = list(concept2id.keys())
        
        embeds_disease = torch.tensor([]).to(device)
        eval_model.to(device)

        for i in tqdm(range(0, len(query), 8)):
            inputs = eval_tokenizer(query[i:i+8], 
                                    padding=True, 
                                    truncation=True, 
                                    max_length=128, 
                                    return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = eval_model(**inputs)
            embeds_disease = torch.cat((embeds_disease, outputs.last_hidden_state[:,0,:]), 0)

        embeds_disease = embeds_disease.cpu().detach().numpy()
        torch.save(embeds_disease, args.orpha_checkpoints)
        
        embeds_disease = torch.tensor(embeds_disease)
    
    return embeds_disease

def topk_similarity(embeddings1, embeddings2, k=10):
    """
    Compute the top-k similarity between two sets of embeddings using PyTorch.
    """
    topk_values = []
    topk_indices = []

    # Normalize the embeddings to use cosine similarity
    embeddings1 = F.normalize(embeddings1, p=2, dim=1)
    embeddings2 = F.normalize(embeddings2, p=2, dim=1)

    # Iterate over each embedding in the first set
    for emb1 in embeddings1:
        # Calculate cosine similarity between this embedding and all embeddings in the second set
        similarities = torch.matmul(embeddings2, emb1)

        # Find the top-k highest similarity values
        values, indices = torch.topk(similarities, k, largest=True)

        topk_values.append(values)
        topk_indices.append(indices)

    return topk_indices, topk_values

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))