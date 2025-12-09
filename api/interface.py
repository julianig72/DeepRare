from openai import OpenAI
import anthropic
import google.generativeai as genai

class Openai_api:
    def __init__(self, api_key, model):

        self.client = OpenAI(
            api_key=api_key
        )
        self.model = model

        self.gpt4_tokens = 0
        self.chatgpt_tokens = 0
        self.gpt_4o_mini_tokens = 0

    def get_completion(self, system_prompt, prompt, seed=42):
        try:       
            completion = self.client.chat.completions.create(
                model=self.model,
                seed=seed,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
            
            return str(completion.choices[0].message.content)
        except Exception as e:
            print(e)
            return None
        
    def openai_summarize(self, text: str):
        try:
            output = self.get_completion("Assume you are a doctor, please summarize these medical article into a paragraph, only keep key message, mainly focus on the phenotype and related disease.", 
                                        text)
            if 'not a medical-related page' in output.lower():
                return ""
            else:
                return output
        except:
            print("Error in summarizing the text. Return the first 1000 characters.")
            return text[:1000]
    
    def mini_completion(self, system_prompt, prompt, seed=42):
        try:       
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                seed=seed,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
            
            return str(completion.choices[0].message.content)
        except Exception as e:
            print(e)
            return None
        
    def get_embedding(self, text: str, model="text-embedding-3-small") -> list[float]:
        return self.client.embeddings.create(input=[text], model=model).data[0].embedding

class deepseek_api:
    def __init__(self, api_key, model):

        self.client = OpenAI(
                api_key=api_key, 
                base_url="https://api.deepseek.com",
                )
        if model == 'deepseek-v3-241226':
            self.model = "deepseek-chat"
        elif model == 'deepseek-r1-250120':
            self.model = "deepseek-reasoner"
        
    def get_completion(self, system_prompt, prompt, seed=42):
        try:       
            print("deepseek model: ", self.model)
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            
            return str(completion.choices[0].message.content)
        except Exception as e:
            print(e)
            return None

class gemini_api:
    def __init__(self, api_key, model):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def get_completion(self, system_prompt, prompt, seed=42):
        try:       
            # Combine system prompt and user prompt
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
            response = self.model.generate_content(full_prompt)
            return str(response.text)
        except Exception as e:
            print(e)
            return None

class claude_api:
    def __init__(self, api_key, model):
        self.client = anthropic.Anthropic(
            api_key=api_key
        )
        self.model = model
        
    def get_completion(self, system_prompt, prompt, seed=42):
        try:       
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return str(message.content[0].text)
        except Exception as e:
            print(e)
            return None