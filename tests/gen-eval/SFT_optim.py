from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from rouge_score import rouge_scorer
from sklearn.model_selection import KFold
from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorWithPadding, StoppingCriteria, StoppingCriteriaList, TrainingArguments, Trainer
from tqdm import tqdm
import bert_score, json, torch
import numpy as np
import pandas as pd


# ===================
# configs + load data 
# ===================
K = 3
KF = KFold(n_splits=K, shuffle=True, random_state=42)
MODEL_NAME = "google/gemma-3-4b-it"

dataset = load_dataset("json", data_files="augmented_check_production.json")["train"]

# lora config:
lora_config = LoraConfig(
    r=8, 
    lora_alpha=16, 
    target_modules=["q_proj", "v_proj"], 
    lora_dropout=0.05, 
    bias="none", 
    task_type="CAUSAL_LM"
)


# ===================
# tokenizer +  tokenization func.
# ===================
gemma_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


def tokenize(ex):
    instruction = f"### Instruction:\n{ex['instruction']}\n\n### Response:\n"
    response = ex["output"]+ "\n### End"

    instruction_tokens = gemma_tokenizer(
        instruction,
        truncation=True,
        max_length=2048,
        add_special_tokens=False
    )

    response_tokens = gemma_tokenizer(
        response,
        truncation=True,
        max_length=2048,
        add_special_tokens=False
    )

    input_ids = instruction_tokens["input_ids"] + response_tokens["input_ids"]
    attention_mask = [1] * len(input_ids)

    # istruction is masked with -100: 
    labels = [-100] * len(instruction_tokens["input_ids"]) + response_tokens["input_ids"]

    return {"input_ids": input_ids, "attention_mask": attention_mask,"labels": labels}


# ===================
# data collator
# ===================
def data_collator(features):
    max_len = max(len(f["input_ids"]) for f in features)

    def pad(seq, pad_val):
        return seq + [pad_val] * (max_len - len(seq))

    return {
        "input_ids": torch.tensor(
            [pad(f["input_ids"], gemma_tokenizer.pad_token_id) for f in features]
        ),
        "attention_mask": torch.tensor(
            [pad(f["attention_mask"], 0) for f in features]
        ),
        "labels": torch.tensor(
            [pad(f["labels"], -100) for f in features]
        ),
    }


# =========================
# stopping criteria (### End)
# =========================
class StopOnTokens(StoppingCriteria):
    def __init__(self, stop_ids):
        self.stop_ids = stop_ids

    def __call__(self, input_ids, scores, **kwargs):
        return input_ids[0][-len(self.stop_ids):].tolist() == self.stop_ids


stop_ids = gemma_tokenizer("### End", add_special_tokens=False).input_ids
stopping_criteria = StoppingCriteriaList([StopOnTokens(stop_ids)])


# ===================
# text cleaning
# ===================
def clean_text(text):
    for t in [
        "### Response:",
        "### Instruction:",
        "### End:",
        "###",
    ]:
        text = text.replace(t, "")
    return text.strip()


# ===================
# training loop w/ CV
# ===================
all_fold_scores = []

for fold, (train_idx, val_idx) in enumerate(KF.split(dataset)):
    print(f"\n===== Fold {fold+1}/{K} =====")

    train_ds = dataset.select(train_idx)
    val_ds   = dataset.select(val_idx)

    # tokenize
    tokenized_train = train_ds.map(tokenize)
    tokenized_val   = val_ds.map(tokenize)

    # load base model + create peft model
    gemma_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16, device_map="auto")

    peft_model = get_peft_model(gemma_model, lora_config)

    # train
    training_args = TrainingArguments(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=2,
        learning_rate=2e-5,
        fp16=True,
        logging_steps=10,
        output_dir=f"./lora-out_alt{fold+1}",
        report_to="none"
    )
    
    trainer = Trainer(
        model=peft_model,
        args=training_args,
        train_dataset=tokenized_train,
        data_collator=data_collator
    )

    trainer.train()

    peft_model.save_pretrained(f"ft-gemma_alt{fold+1}")
    gemma_tokenizer.save_pretrained(f"ft-gemma_alt{fold+1}")

    # inference (on tokenized valid. set)
    references, predictions = [], []

    peft_model.eval()
    with torch.no_grad():
        for ex in tqdm(tokenized_val):
            # reference
            label_ids = [i for i in ex["labels"] if i != -100]
            ref = gemma_tokenizer.decode(label_ids, skip_special_tokens=True)
            references.append(clean_text(ref))

            # prompt
            prompt = f"### Instruction:\n{ex['instruction']}\n\n### Response:\n"
            inputs = gemma_tokenizer(prompt, return_tensors="pt").to(peft_model.device)

            outputs = peft_model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_new_tokens=150,
                do_sample=False,                     
                stopping_criteria=stopping_criteria,
                pad_token_id=gemma_tokenizer.eos_token_id,
                eos_token_id=gemma_tokenizer.eos_token_id,
                repetition_penalty=1.2  
                )
            gen_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
            pred = gemma_tokenizer.decode(gen_tokens, skip_special_tokens=True)
            cleaned = clean_text(pred)
            predictions.append(cleaned)

    # bert score
    P, R, F1 = bert_score.score(
        predictions,
        references,
        lang="it",
        rescale_with_baseline=True
    )

    # rougeL
    rl_scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    rl_p = []
    rl_r = []
    rl_f1 = []

    for ref, pred in zip(references, predictions):
        scores = rl_scorer.score(ref, pred)
        rl_p.append(scores["rougeL"].precision)
        rl_r.append(scores["rougeL"].recall)
        rl_f1.append(scores["rougeL"].fmeasure)
        
    rl_p = np.array(rl_p)
    rl_r = np.array(rl_r)
    rl_f1 = np.array(rl_f1)
    
    fold_result = {
        "fold": fold + 1,
        "bert_precision": P.mean().item(),
        "bert_recall": R.mean().item(),
        "bert_f1": F1.mean().item(),
        "rouge_precision": rl_p.mean(),
        "rouge_recall": rl_r.mean(),
        "rouge_f1": rl_f1.mean()
    }

    print(fold_result)
    all_fold_scores.append(fold_result)

#======================================
df = pd.DataFrame(all_fold_scores)
print("\n===== Cross-Validation Results =====")
print(df)
print("\nMean scores:")
print(df.mean(numeric_only=True))
print("\nStd deviation:")
print(df.std(numeric_only=True))
