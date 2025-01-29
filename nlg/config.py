import argparse, os, torch
from jinja2 import Template, Environment, FileSystemLoader
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from typing import Text


class LLM:
        def __init__(self, model_id="swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA") -> None:
            self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")#, torch_dtype='auto')
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.generation_config.pad_token_id = self.tokenizer.eos_token_id
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model_name = model_id.split("/")[1]
            if self.device == "cpu":
                os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
        def __repr__(self):
            return f"MODEL FULL NAME: {self.model_name}"


        def create_prompt(self, intent, utterance, energy_data):
            system = "Sei un assistente AI per la lingua italiana. Rispondi nella lingua usata per la domanda in modo chiaro, diretto e completo. Attieniti strettamente alle istruzioni fornite e riporta la tua risposta in modo conciso, senza aggiungere ulteriori commenti o spiegazioni."
            env = Environment(loader=FileSystemLoader("templates"))
            template = env.get_template("template.j2")
            context = {"intent":intent, "utterance": utterance, "energy_data": energy_data}
            user = template.render(**context)
            complete = [{"role": "system", "content":f"{system}"},{"role": "user", "content":f"{user}"}]
            formatted = self.tokenizer.apply_chat_template(complete, tokenize=False, add_generation_prompt=True)

            return formatted


        def inference(self, prompt):
            pipe = pipeline(model=self.model,
                            tokenizer=self.tokenizer,
                            return_full_text=False,  
                            task='text-generation',
                            do_sample=True,
                            top_k=40,
                            top_p=0.9,
                            num_return_sequences=1,
                            temperature=0.6,
                            device_map="auto",
                            torch_dtype='auto',
                            max_new_tokens=100  # max number of tokens to generate in the output
                            )
            #prompt = self.prompt_filling(data)
            result = pipe(prompt)[0]["generated_text"]
            #print(result[0]["generated_text"])

            return result             
    

if __name__ == "__main__":
    llm = LLM()
    intent_ex= "check_consumption"
    utterance_ex="voglio vedere i consumi"
    data_ex= "- energia totale utilizzata dalla casa: 11.11 kWh \n - energia totale acquistata dalla rete: 4.47 kWh \n - potenza istantanea fornita dall'impianto solare: 0.00 kW \n - potenza istantanea fornita dalla batteria: 0.29 kW \n - potenza istantanea fornita dalla rete: 0.11 kW \n - potenza totale: 0.40 kW"
    prompt = llm.create_prompt(intent_ex, utterance_ex, data_ex)
    print(prompt)
    response = llm.inference(prompt)
    print(response)

    