import argparse, os, random, torch
import pandas as pd
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, set_seed
from utils import *
set_seed(42)


class LLM:
        def __init__(self, model_id, data_path, shot_no) -> None:
            self.name = model_id.split("/")[-1]
            model_path, model_name = model_id.split("/")
            self.data_path=data_path
            self.shot_no=shot_no
            self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")#, torch_dtype='auto')
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.model_max_length=1024
            self.model.generation_config.pad_token_id = self.tokenizer.eos_token_id
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if self.device == "cpu":
                os.environ["TOKENIZERS_PARALLELISM"] = "false"
                
    
        def __repr__(self):
            return f"MODEL FULL NAME: {self.name} \n {self.model.generation_config}"


        def prompt_filling(self, input_utterance, examples=[]):
            system = "Sei un an assistente AI per la lingua italiana. Rispondi nella lingua usata per la domanda in modo chiaro, diretto e completo. Attieniti strettamente alle istruzioni fornite e riporta la tua risposta nel formato richiesto, senza aggiungere ulteriori commenti o spiegazioni."
            context = read_from_file()
            instruction = f"Sulla base delle informazioni appena fornite, restuituisci solo la rappresentazione formale dei vincoli per l'enunciato seguente. Enunciato: {input_utterance}\n Rappresentazione formale: \n"
            
            if self.shot_no > 0:
                context += "".join(examples)
            
            user_message = context+instruction
            prompt = [{"role": "system", "content":f"{system}"},{"role": "user", "content":f"{user_message}"}]

            prompt = self.tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
            return prompt     


        def inference(self, prompt_file):
            
            data=self.read_dataset(prompt_file)
            utterances = data["utterances"]
            
            if self.shot_no > 0:
                self.tokenizer.model_max_length += (self.shot_no*128)
                print(self.tokenizer.model_max_length)
                examples= data["additional_info"]
                prompt = [self.prompt_filling(utterance, examples) for utterance in utterances]
            else:
                prompt = [self.prompt_filling(utterance) for utterance in utterances]

            print(prompt[0])
            #"""
            inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False, padding='max_length')
            input_ids = inputs['input_ids']
            input_token_len = input_ids.shape[-1]
            print(input_token_len)
            for i in range(len(prompt)):
                print(inputs['attention_mask'][i])
            results=[]
            outputs = self.model.generate(input_ids=input_ids, 
    attention_mask=inputs['attention_mask'], max_new_tokens=30, top_p=0.9, temperature=0.1, top_k=20, do_sample=True)
            print(outputs.shape)
            with open(f"out_{prompt_file}", "w", encoding="utf-8") as out:
                for i in range(len(prompt)):
                    res = self.tokenizer.decode(outputs[i][input_token_len:], skip_special_tokens=True)
                    results.append(res)
                    out.write(res+"\n")
                
            return results
            #"""


        def read_dataset(self, add_prompt_file_path=""):
            """
            prende da file jsonl gli enunciati di test e da file esterno il prompt associato al dato setting
            TODO: preparare un file di prompt per ciascun setting: 1/5 esempi (base+CoT)
            """
            data = pd.read_json(self.data_path, lines=True)
            dataset = Dataset.from_pandas(data)
            test = dataset.filter(lambda d: d["split"]=="test" and d["constraint_representation"] != "-")
            constraint_repr=test["constraint_representation"]
            labeled_utterances=test["xml_tagged_preferences"]

            if self.shot_no == 0:
                return {"utterances":labeled_utterances, "constraints": constraint_repr}
            else:
                try:
                    add_info = read_from_file(add_prompt_file_path)
                    return {"utterances":labeled_utterances, "additional_info": [add_info], "constraints": constraint_repr}    
                except:
                    print("It seems like you didn't pass a prompt file path. If one or more examples are to be included in the prompt, please put them in a text file and pass the file as argument using the -p flag")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", default="swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA", help="model path as it appears in the HF page")
    parser.add_argument("-d", "--data_path", default="nl2optim.jsonl", help="Data file path")
    parser.add_argument("-s", "--shots", default=0, type=int)
    parser.add_argument("-p", "--prompt_path", required=False)
    args = parser.parse_args()
    llm = LLM(args.model, args.data_path, args.shots)
    print(llm)
    llm.read_dataset()
    #llm.inference(args.prompt_path)
