import torch
import re
import os
import numpy as np

from utils import topk_similarity, cosine_similarity

from tools.web_search import DuckDuckGoSearchTool, BingSearchTool, GoogleSearchTool
from tools.page_fetch import fetch_page_content_and_summarize
from tools.hpo_search import HPOSearchTool
from tools.search_pubmed import search_PubMed
from tools.search_arxiv import search_Arxiv
from tools.search_wiki import search_Wiki
from tools.pubcase_finder import PubCaseFinderSearchTool
from tools.phenobrain_api import PhenobrainAPITool
from tools.omim_search import OMIMSearchTool
from tools.llm_agent import Check_Agent, Check_Patient_Agent
from tools.exomizer_inference import ExomiserRunner
from tools.vep_api_analysis import run_vep_diagnosis


def get_pheonotype_knowledge(args, phenotypes, phenotype_ids, mini_handler):
    phenotype_knowledge = ''
    for i, pheno in enumerate(phenotypes):

        # knowledge_1 : Web Search
        if args.search_engine == 'google':
            web_result = GoogleSearchTool(args, pheno, mini_handler, read_content=True, return_num=2)
        elif args.search_engine == 'duckduckgo':
            web_result = DuckDuckGoSearchTool(args, pheno, mini_handler, read_content=True, return_num=2)
        else:
            web_result = BingSearchTool(args, pheno, mini_handler, read_content=True, return_num=2)
        print('completed web search for phenotype')
        
        # knowledge_2 : HPO Search
        hpo_result = HPOSearchTool(args, phenotype_ids[i])
        print('completed hpo search')

        # knowledge_3 : pubmed_search
        pubmed_result = search_PubMed(query=pheno)
        print('completed pubmed search')

        phenotype_knowledge += f"Here is the knowledge about phenotype {pheno}:\n"
        phenotype_knowledge += f"Web Search:\n"
        phenotype_knowledge += '\n'.join(web_result)
        phenotype_knowledge += f"PubMed Search:\n"
        phenotype_knowledge += '\n'.join(pubmed_result)
        phenotype_knowledge += f"HPO gives top5 related diseases about {pheno}:\n"
        phenotype_knowledge += '\n'.join(hpo_result)

    return phenotype_knowledge
    

def get_orphanet_id_from_disease(args, result, embeds_disease, concept2id, orpha2omim, 
                                 eval_model, eval_tokenizer, orphanet_data, patient_info, 
                                 search_depth, handler, mini_handler, tmp_save, similar_case_detailed):
    
    diseases = re.findall(r'\*\*(.*?)\*\*', result)
    
    # if brackets in the disease name
    diseases_new = []
    for i in range(len(diseases)):
        if '(' in diseases[i]:
            diseases_new.append(diseases[i].split('(')[0])
            diseases_new.append(diseases[i].split('(')[1].split(')')[0])
        else:
            diseases_new.append(diseases[i])
            
    diseases_new = [disease.strip() for disease in diseases_new if disease.strip()]
    diseases = diseases_new

    if not diseases or embeds_disease is None or not concept2id:
        return [], '', tmp_save
    
    # use similarity matching agent to find ORPHANET ID
    with torch.no_grad():
        encoded = eval_tokenizer(
            diseases, 
            truncation=True, 
            padding=True, 
            return_tensors='pt', 
            max_length=36,
        )

        embeds_word = eval_model(**encoded).last_hidden_state[:, 0, :]
        
    topk_indices, _ = topk_similarity(embeds_word, embeds_disease, k=1)

    for i in range(len(topk_indices)):
        topk_indices[i] = topk_indices[i].cpu().numpy().tolist()

    # map index to name
    keys_list = list(concept2id.keys())
    value_list = list(concept2id.values())
    
    topk_disease_name = [[keys_list[idx] for idx in item] for item in topk_indices]
    topk_disease = [[value_list[idx] for idx in item] for item in topk_indices]
    topk_disease = [item[0] for item in topk_disease]
    topk_disease_name = [item[0] for item in topk_disease_name]
    
    
    # Acquire disease knowledge
    for i, disease_id in enumerate(topk_disease):
        
        disease_name = topk_disease_name[i]
        
        if disease_id in tmp_save:
            print(f"Found in the cache: {disease_name}")
            continue
        
        print(f"Searching for disease: {disease_id, disease_name}")
        
        # knowledge_1 : ORPHANET Search input: orpha id
        try:
            orpha_knowledge = orphanet_data.get(disease_id)
            print('Searching for disease knowledge')
            disease_knowledge = fetch_page_content_and_summarize(args, orpha_knowledge['expert_link'], mini_handler, screenshot=args.screenshots)
            disease_related_hpo = '; '.join([' '.join(orpha_knowledge['hpo_associations'][i]) for i in range(len(orpha_knowledge['hpo_associations']))])
            
            disease_knowledge_collection = "Disease Name: " + orpha_knowledge['name'] + '\n' + \
                                            "Expert Knowledge: " + disease_knowledge + '\n' + \
                                            "HPO Associations: " + disease_related_hpo + '\n' + \
                                            "Database Link: " + orpha_knowledge['expert_link'] + '\n' + \
                                            "Data Source: ORPHANET\n\n"
            try:
                omim_id = orpha2omim.get(disease_id)
                print('Searching for OMIM knowledge')
                OMIM_knowledge = OMIMSearchTool(omim_id)
                disease_knowledge_collection += '\n---\n' + OMIM_knowledge 
            except:
                print('Not found in OMIM')
                continue
            
            check_output = Check_Agent(patient_info, disease_name, disease_knowledge_collection, handler, similar_case_detailed)
            
            # judge_result.append(check_output[0])
            # judgements.append(check_output[1])
            tmp_save[disease_id] = {'disease_name': disease_name,
                                    'judge_result': check_output[0], 
                                    'judgements': check_output[1]}
    
            continue
        except Exception as e:
            print('Not found in ORPHANET')
            pass
        
        # knowledge_2 : OMIM Search input: omim id
        try:
            omim_id = orpha2omim.get(disease_id)
            print('Searching for OMIM knowledge')
            OMIM_knowledge = OMIMSearchTool(omim_id)
            check_output = Check_Agent(patient_info, disease_name, OMIM_knowledge, handler, similar_case_detailed)
            # judge_result.append(check_output[0])
            # judgements.append(check_output[1])
            tmp_save[disease_id] = {'disease_name': disease_name,
                                    'judge_result': check_output[0], 
                                    'judgements': check_output[1]}
            continue
        except Exception as e:
            print('Not found in OMIM')
            pass  

        
        # # knowledge_3 : uptodate_search
        # if args.uptodate_pwd != '':
        #     try:
        #         print('Searching for uptodate knowledge')
        #         uptodate_guideline = UptodateSearchTool(args, disease_name)
        #         check_output = Check_Agent(patient_info, disease_name, uptodate_guideline, handler)
        #         # judge_result.append(check_output[0])
        #         # judgements.append(check_output[1])
        #         tmp_save[disease_id] = {'disease_name': disease_name,
        #                             'judge_result': check_output[0], 
        #                             'judgements': check_output[1]}
        #         continue
        #     except Exception as e:
        #         print('Not found in Uptodate')
                # pass
        
        # knowledge_4 : pubmed_search
        try:
            print('Searching for pubmed knowledge')
            pubmed_result = search_PubMed(query=disease_name, max_results=2*search_depth, mini_handler = mini_handler)
            check_output = Check_Agent(patient_info, disease_name, pubmed_result, handler, similar_case_detailed)
            # judge_result.append(check_output[0])
            # judgements.append(check_output[1])
            tmp_save[disease_id] = {'disease_name': disease_name,
                                    'judge_result': check_output[0], 
                                    'judgements': check_output[1]}
            continue
        except Exception as e:
            print('Not found in Pubmed')
            pass
        
        # knowledge_5 : arxiv_search
        try:
            print('Searching for arxiv knowledge')
            arxiv_result = search_Arxiv(query=disease_name, max_results=2*search_depth, mini_handler = mini_handler)
            check_output = Check_Agent(patient_info, disease_name, arxiv_result, handler, similar_case_detailed)
            # judge_result.append(check_output[0])
            # judgements.append(check_output[1])
            tmp_save[disease_id] = {'disease_name': disease_name,
                                    'judge_result': check_output[0], 
                                    'judgements': check_output[1]}
            continue
        except Exception as e:
            print('Not found in Arxiv')
            pass
        
        # knowledge_6 : wiki_search
        try:
            print('Searching for wiki knowledge')
            wiki_result = search_Wiki(query=disease_name, max_results=1*search_depth, mini_handler = mini_handler)
            check_output = Check_Agent(patient_info, disease_name, wiki_result, handler, similar_case_detailed)
            # judge_result.append(check_output[0])
            # judgements.append(check_output[1])
            tmp_save[disease_id] = {'disease_name': disease_name,
                                    'judge_result': check_output[0], 
                                    'judgements': check_output[1]}
            continue
        except Exception as e:
            print('Not found in Wiki')
            pass
        
        
    judgements_content  = ''
    judge_result = []
    for disease_id in tmp_save:
        judgements_content += f"[ Disease Name: {tmp_save[disease_id]['disease_name']}\n"
        judgements_content += f"Judgement: {tmp_save[disease_id]['judgements']} ]\n"
        judge_result.append(tmp_save[disease_id]['judge_result'])
        
    return judge_result, judgements_content, tmp_save


def similar_case_search(df, product_description, embeding_handler, n=3,  pprint=True):

    if df is None or df.empty:
        return df

    embed = embeding_handler(product_description)
    
    df['similarities'] = df.embedding.apply(lambda x: cosine_similarity(eval(x), embed))
    res = df.sort_values('similarities', ascending=False).head(n)
    
    res.reset_index(drop=True, inplace=True)
    return res
    

def get_similar_cases(args, head_similar_cases, eval_model, eval_tokenizer, patient_info,  handler, topk):
    
    if head_similar_cases is None or head_similar_cases.empty:
        return ""

    query = [[patient_info, i] for i in list(head_similar_cases['case_report'])]

    if not query:
        return ""

    inputs = eval_tokenizer(query, 
                            padding=True, 
                            truncation=True, 
                            max_length=128, 
                            return_tensors="pt").to(args.device)
    
    eval_model.to(args.device)
    with torch.no_grad():
        logits = eval_model(**inputs).logits.squeeze(dim=1).cpu().detach().numpy()
    eval_model.to('cpu')
    # Higher scores indicate higher relevance to the query, so find the top 3 highest scores rank
    top_3n_indices = list(np.argsort(logits)[-topk:][::-1])
    
    similar_case_detailed = ""
    
    for i, index in enumerate(top_3n_indices):
        # check if the case is similar
        if Check_Patient_Agent(patient_info, head_similar_cases.iloc[index]['case_report'], handler):
            if str(head_similar_cases.iloc[index]['diagnosis']) == 'nan':
                continue
            similar_case_detailed += f"Here is a similar case {i}: A patient with the following symptoms: " + '\n'
            similar_case_detailed += head_similar_cases.iloc[index]['case_report'] + '\n'
            similar_case_detailed += "The diagnosis is: " + head_similar_cases.iloc[index]['diagnosis'] + '\n'
    
    return similar_case_detailed


def make_diagnosis(args, i, patient, rare_prompt, orphanet_data, concept2id, orpha2omim, similar_cases, 
                   embeds_disease, eval_model, eval_tokenizer, retr_model, retr_tokenizer, 
                   handler, mini_handler, embedding_handler):
    
    # exclude the args.dataset_name+'_'+i in the similar_cases
    similar_cases = similar_cases[~(similar_cases['_id']==(args.dataset_name+'_'+str(i)))]
    
    # Patient information
    patient_info = patient[0]
    golden_diagnosis = patient[1]
    phenotypes = patient[2]
    phenotype_ids = patient[3]
    vcf_path = patient[4]

    # set up the system prompt and prompt
    system_prompt, prompt = rare_prompt.diagnosis_prompt(patient_info)

    # print(f"patient {i} system_prompt: {system_prompt}")
    print(f"patient {i} prompt: {prompt}")
  
    ### second: get diagnosis API response
    phenotype_id_list = [p.strip() for p in phenotype_ids.split(',') if p.strip()] if isinstance(phenotype_ids, str) else phenotype_ids
    diagnosis_api_response = ""
    if phenotype_id_list:
        try:
            diagnosis_api_response += PubCaseFinderSearchTool(args, phenotype_id_list)
        except Exception as e:
            print(f"PubCaseFinder error: {e}")
            diagnosis_api_response += "PubCaseFinder: unavailable"
        diagnosis_api_response += ' \n'
        try:
            phenobrain_result = PhenobrainAPITool(phenotype_id_list)
            if phenobrain_result:
                diagnosis_api_response += phenobrain_result
        except Exception as e:
            print(f"Phenobrain error: {e}")
            diagnosis_api_response += "Phenobrain: unavailable"
    else:
        diagnosis_api_response = "No HPO IDs provided for API-based diagnosis."
    
    ### third: dynamic diagnosis response
    flag = True
    tmp_save = dict()
    
    search_depth = 1
    
    while flag:
        
        ## Web Diagnosis
        if args.search_engine == 'google':
            web_diagnosis = GoogleSearchTool(args, patient_info, mini_handler, read_content=True, return_num=5*search_depth)
        elif args.search_engine == 'duckduckgo':
            web_diagnosis = DuckDuckGoSearchTool(args, patient_info, mini_handler, read_content=True, return_num=5*search_depth)
        else:  
            web_diagnosis = BingSearchTool(args, patient_info, mini_handler, read_content=True, return_num=5*search_depth)
        print('completed web search')
        ## LLM Diagnosis
        llm_response = handler.get_completion(system_prompt, prompt)
        if not llm_response:
            llm_response = "LLM diagnosis unavailable."
        print('completed llm search')
        
        ## Similar Cases
        # retrieve by openai text-embedding-3-small to get top 20 similar cases
        head_similar_cases = similar_case_search(similar_cases, patient_info, embedding_handler, n=50)
        
        # retrieve by medcpt to get top 3 similar cases    
        similar_case_detailed = get_similar_cases(args, head_similar_cases, retr_model, retr_tokenizer, patient_info, handler, topk=3*search_depth )

        ### Summarize and diagnosis
        memory_1 =  f"""You have access to the following context:

- **Online knowledge** (with titles and URLs): {web_diagnosis}
- **LLM-generated diagnoses**: {llm_response}
- **Diagnosis API results**: {diagnosis_api_response}
- **Similar cases** (detailed): {similar_case_detailed}
- **Prompt details:** {prompt.split('Enumerate the top 5 most likely diagnoses.')[0]}

---
Based on the above and your knowledge, enumerate the **top 5 most likely rare disease diagnoses** for this patient. 

**For each diagnosis, use the following format:**

## **DIAGNOSIS NAME** (Rank #X/5)

### Diagnostic Reasoning:
- Provide 2-3 concise sentences explaining why this rare disease fits the clinical picture.
- Integrate evidence from all available sources (online knowledge, similar cases, LLM outputs, and API results).
- Support your reasoning with specific, in-text citations in [X] format, referencing the most relevant sources (including specific similar cases, articles, or diagnostic tools).
- Briefly discuss the pathophysiological basis for the diagnosis, citing relevant literature or case evidence.

---

**After listing all 5 diagnoses, include a reference section:**

## References:
- Number each reference in the order it is first cited ([1], [2], ...).
- Only include sources you directly cited in your diagnostic reasoning above.
- For each reference, should provide:
    a. Source type (e.g., medical guideline, similar case, literature, diagnosis assisent tool...) 
    b. Use 3-4 sentences to describe of the content and its relevance.
    c. For articles or literature, include the title and URL if provided.
- Every in-text citation [X] in your reasoning should correspond to a numbered entry in your reference list.
- Try to cover as more sources and references.
- Do not repeat!!

---

**Key Instructions:**
1. Always use in-text citations in [X] format, matching only the references you actually cite in your reasoning.
2. Each diagnosis must be a rare disease (**bolded** using markdown).
3. Rank from most (#1) to least (#5) likely.
4. Integrate information from all provided sources (medical literature, similar cases, and judgement analyses) wherever appropriate.
5. Do **not** copy or invent references—only include those present in the provided materials.
"""

                    
        result = handler.get_completion(system_prompt, memory_1)
        if not result:
            result = "Unable to generate diagnosis. Please check API key and try again."
        
        ### Reflected Diagnosis
        judge_result, judgements, tmp_save = get_orphanet_id_from_disease(args, result, embeds_disease, concept2id, orpha2omim, 
                                                                        eval_model, eval_tokenizer, orphanet_data, patient_info, 
                                                                        search_depth, handler, mini_handler, tmp_save, similar_case_detailed)
        
        # ipdb.set_trace()
        # if all the diagnosis are incorrect, then change the search depth
        if sum(judge_result) > 0:
            flag = False
        else:
            search_depth += 1
            if search_depth >= 2:
                flag = False
                result = "Theses diagnoses are not mostly incorrect, please check the patient information carefully."
                

    memory_2 = f"""
You have access to the following information:
- Patient presentation: {prompt.split('Enumerate the top 5 most likely diagnoses.')[0]}
- Similar cases: {similar_case_detailed}
- Primary diagnosis results (with references): {result}
- Disease Reflection (with references): {judgements}

**Task:**  
Based on all the above, enumerate the top 5 most likely rare disease diagnoses for this patient.

---

**For each diagnosis, follow this format exactly:**

## **DISEASE NAME** (Rank #X/5)

### Diagnostic Reasoning:
- Provide 3-4 sentences explaining why this diagnosis fits the patient's presentation.
- Specify which patient symptoms and findings support this diagnosis.
- Clearly explain the underlying pathophysiological mechanisms (briefly).
- Integrate and **cite specific evidence** from the provided references (including medical literature, similar cases, or judgement analyses), using in-text [X] citation style.
- Try to cite as more sources and references but do not add hallucination content.

---

**After listing all 5 diagnoses, include a reference section:**

## References:
- Number each reference in the order it is first cited ([1], [2], ...).
- Only include sources you directly cited in your diagnostic reasoning above.
- For each reference, should provide:
    a. Source type (e.g., medical guideline, similar case, literature, diagnosis assisent tool...) ( Do not use source type: "Judgement analysis", "Disease Reflection" )
    b. Use 3-4 sentences to describe of the content and its relevance.
    c. For articles or literature, include the title and URL if provided.
- Every in-text citation [X] in your reasoning should correspond to a numbered entry in your reference list.
- Try to cover as more sources and references.
- Do not repeat!!

---

**IMPORTANT GUIDELINES:**

1. Each diagnosis must be a rare disease (**bolded** using markdown).
2. Rank from most (#1) to least (#5) likely.
3. Integrate information from all provided sources (medical literature, similar cases, and judgement analyses) wherever appropriate.
4. Do **not** copy or invent references—only include those present in the provided materials.
5. Remember to add the summary of the content, url for each reference.
"""
    
    final_diagnois = handler.get_completion(system_prompt, memory_2 )
    if not final_diagnois:
        final_diagnois = result

    # Run genetic variant analysis on VCF
    mutation_details = ""
    variant_data = []
    if vcf_path: 
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        jar_path = os.path.join(SCRIPT_DIR, args.exomiser_jar) if args.exomiser_jar else ""
        if jar_path and os.path.exists(jar_path):
            print(f"Running Exomiser (jar found)")
            exomiser = ExomiserRunner(
                exomiser_jar_path=jar_path,
                output_dir=args.exomiser_save_path
            )
            exomiser_result = exomiser.run_diagnosis_inference(
                    vcf_path=vcf_path,
                    hpo_ids=phenotype_ids,
                    patient_info=patient_info,
                    preliminary_diagnosis=final_diagnois,
                    api_interface=handler,
                )
            if exomiser_result.get("ai_diagnosis"):
                final_diagnois = exomiser_result["ai_diagnosis"]
            mutation_details = exomiser_result.get("exomiser_summary", "")
        else:
            print(f"Exomiser not available, using VEP API for variant analysis...")
            try:
                vep_result = run_vep_diagnosis(
                    vcf_path=vcf_path,
                    hpo_ids=phenotype_ids if isinstance(phenotype_ids, list) else [p.strip() for p in phenotype_ids.split(',') if p.strip()],
                    patient_info=patient[0],
                    preliminary_diagnosis=final_diagnois,
                    api_interface=handler,
                )
                if vep_result.get("ai_diagnosis"):
                    final_diagnois = vep_result["ai_diagnosis"]
                mutation_details = vep_result.get("vep_summary", "")
                variant_data = vep_result.get("top_candidates", [])
            except Exception as e:
                print(f"VEP analysis failed: {e}")


    ### Return the patient information
    patient_info = {}
    patient_info["patient_info"] = patient[0]
    patient_info["golden_diagnosis"] = golden_diagnosis
    patient_info["phenotypes"] = phenotypes
    patient_info["phenotype_ids"] = phenotype_ids
    patient_info["diagnosis_api_response"] = diagnosis_api_response
    patient_info["web_diagnosis"] = web_diagnosis
    patient_info["zero_shot_llm_response"] = llm_response
    patient_info["similar_cases"] = similar_case_detailed
    patient_info["first_round_result"] = result
    patient_info["judge_result"] = judge_result
    patient_info["judgements"] = judgements
    patient_info["final_diagnois"] = final_diagnois
    patient_info["mutation_details"] = mutation_details
    patient_info["variant_data"] = variant_data

    return patient_info
