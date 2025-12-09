import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import random
import time
from transformers import AutoModel, AutoTokenizer, AutoModelForSequenceClassification

from utils import set_up_args, set_up_data
from diagnosis import make_diagnosis
from api.interface import Openai_api, gemini_api, deepseek_api, claude_api


# define the LLM handler based on the selected model
class LLM_handler:
    def __init__(self, args):
        
        if args.model == "openai":
            self.handler = Openai_api(args.openai_apikey, args.openai_model)
        elif args.model == "gemini":
            self.handler = gemini_api(args.gemini_apikey, args.gemini_model)
        elif args.model == "deepseek":
            self.handler = deepseek_api(args.deepseek_apikey, args.deepseek_model)
        elif args.model == "claude":
            self.handler = claude_api(args.claude_apikey, args.claude_model)
        else:
            raise ValueError("Invalid model name.")


def main():
    
    # Set up the argument parser
    args, results_folder = set_up_args()
    
    # Set up the BERT model and tokenizer
    eval_model = AutoModel.from_pretrained(args.bert_model)
    eval_tokenizer = AutoTokenizer.from_pretrained(args.bert_model)
    
    # Set up the retrieval model
    retr_model = AutoModelForSequenceClassification.from_pretrained(args.retrieval_model)
    retr_tokenizer = AutoTokenizer.from_pretrained(args.retrieval_model)
    
    # Set up the dataset, rare_prompt, orphanet_data, concept2id, orpha2omim, similar_cases, embeds_disease
    dataset, rare_prompt, orphanet_data, concept2id, orpha2omim, similar_cases, embeds_disease = set_up_data(args, eval_model, eval_tokenizer)
    
    # Set up the LLM Model
    handler = LLM_handler(args).handler
    
    Openai = Openai_api(args.openai_apikey, args.openai_model)

    mini_handler = Openai.mini_completion
    embedding_handler = Openai.get_embedding

    print("Begin Extraction.....")
    print("total patient: ", len(dataset.patient))
    
        # Create a list of tuples containing the index and patient
    indexed_patients = list(enumerate(dataset.patient))

    # Shuffle the list of tuples
    random.shuffle(indexed_patients)

    # Iterate over the shuffled list
    for i, patient in indexed_patients:
        result_file = os.path.join(results_folder, f"patient_{i}.json")
        if os.path.exists(result_file):
            continue

        time_start = time.time()

        patient_info = make_diagnosis(args, i, patient, rare_prompt, orphanet_data, concept2id, orpha2omim,
                                    similar_cases, embeds_disease, eval_model, eval_tokenizer, retr_model, retr_tokenizer, 
                                    handler, mini_handler, embedding_handler)

        time_end = time.time()

        time_taken = time_end - time_start
        patient_info["time_taken"] = time_taken

        with open(result_file, "w", encoding="utf-8-sig") as f:
            json.dump(patient_info, f, indent=4, ensure_ascii=False)

        print(f"Patient {i} diagnosis completed.")
        

if __name__ == "__main__":
    main()
