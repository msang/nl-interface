import os
import torch
from typing import Optional, Text
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from ollama import Client as OllamaClient
from jinja2 import Environment, FileSystemLoader

# ------------------------------
# Base LLM Wrapper (Abstract)
# ------------------------------
class BaseLLM:
    def create_prompt(self, intent: str, utterance: str, energy_data: str) -> str:
        raise NotImplementedError

    def inference(self, prompt: str) -> str:
        raise NotImplementedError


# ------------------------------
# HuggingFace Model Wrapper
# ------------------------------
class HFLLM(BaseLLM):
    def __init__(self, model_id: str):
        self.model_name = model_id
        self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.generation_config.pad_token_id = self.tokenizer.eos_token_id

    def create_prompt(self, intent, utterance, energy_data):
        if intent == "ask_selling_advice":
            system = "Sei un assistente esperto in comunità energetiche e gestione peer-to-peer dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, senza ridondanze.  Mantieni la risposta sotto i 250 token."
        else:
            system = "Sei un assistente esperto di ottimizzazione energetica. Fornisci risposte brevi ma precise. Non superare i 150 token."

        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("template.j2")
        user = template.render(intent=intent, utterance=utterance, data=energy_data)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return prompt

    def inference(self, prompt: str) -> str:
        gen = pipeline(
            model=self.model,
            tokenizer=self.tokenizer,
            return_full_text=False,
            task="text-generation",
            do_sample=True,
            top_k=40,
            top_p=0.9,
            temperature=0.6,
            max_new_tokens=100,
        )
        return gen(prompt)[0]["generated_text"]


# ------------------------------
# Ollama Model Wrapper
# ------------------------------
class OllamaLLM(BaseLLM):
    def __init__(self, model_name: str):
        self.client = OllamaClient()
        self.model_name = model_name

    def create_prompt(self, intent, utterance, energy_data):
        #template_dir = os.path.join(os.path.dirname(__file__), "templates")
        #env = Environment(loader=FileSystemLoader(template_dir))
        env = Environment(loader=FileSystemLoader('../templates'))
        template = env.get_template("template.j2")
        user = template.render(intent=intent, utterance=utterance, data=energy_data)

        if intent == "ask_selling_advice":
            system = "Sei un assistente esperto in comunità energetiche e gestione peer-to-peer dell’energia su blockchain. Rispondi con linguaggio tecnico ma comprensibile, senza ridondanze.  Mantieni la risposta sotto i 250 token."
        else:
            system = "Sei un assistente esperto di ottimizzazione energetica. Fornisci risposte brevi ma precise. Non superare i 150 token."

        return f"<|system|>\n{system}\n<|user|>\n{user}"

    
    def inference(self, prompt: str) -> str:
        #response = self.client.chat(model=self.model_name, messages=[{"role": "user", "content": prompt}])
        response = self.client.chat(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={"temperature": 0.0}
                    )

        return response['message']['content']


# ------------------------------
# Classe richiamata dal server - fa il routing del modello in base all'intent
# ------------------------------
class LLM:
    def __init__(self):
        self.hf_model = HFLLM("swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA")
        self.ollama_model = OllamaLLM("gemma3:4b-it-qat")  

    def create_prompt(self, intent, utterance, energy_data):
        model = self._select_model(intent)
        return model.create_prompt(intent, utterance, energy_data)

    def inference(self, prompt, intent=None):  # intent opzionale nel caso servisse routing
        model = self._select_model(intent)
        return model.inference(prompt)

    def _select_model(self, intent: Optional[str]):
        if intent == "ask_selling_advice":
            return self.ollama_model
        return self.hf_model
