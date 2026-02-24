import pandas as pd
from bert_score import score
import argparse, os
from typing import List


def compute_bertscore(responses: List[str], references: List[str]):
    P, R, F1 = score(responses, references, lang="it")
    return F1.tolist()


def eval(input_path, output_path):
    print(input_path,output_path)
    df = pd.read_csv(input_path)
    df = df.astype({"tempo_esecuzione":float})
    df["bertscore_f1"] = compute_bertscore(df["risposta"].tolist(), df["gold"].to_list())
    df.to_csv(output_path, index=False)
    #print(df.dtypes)
    return df


def summarize(df):
    
    avg_bert = df["bertscore_f1"].groupby(df["modello"]).mean()
    print(f"Bert score medio per modello: \n {avg_bert}")
    
    avg_gen_time = df["tempo_esecuzione"].groupby(df["modello"]).mean()
    print(f"Tempi di inferenza medi:\n {avg_gen_time}")
    
    #avg_shot = df["bertscore_f1"].groupby(df["shot"]).mean()
    avg_shot = df.groupby(["modello","shot"])["bertscore_f1"].mean()
    print(f"Bert score medio per modello e per setting:\n {avg_shot}")
    
    #avg_intent = df["bertscore_f1"].groupby(df["intent"]).mean()
    avg_intent = df.groupby(["modello","intent"])["bertscore_f1"].mean()
    print(f"Bert score medio per intent:\n {avg_intent}")

    pd.set_option("display.max_rows", None)  # num. illimitato di righe visualizzabili
    avg_intent_time = df.groupby(["modello","intent"])["tempo_esecuzione"].mean()
    print(f"Tempi di inferenza medi per modello e per intent:\n {avg_intent_time}")

    avg_intent_shot = df.groupby(["modello","intent","shot"])["bertscore_f1"].mean()
    print(f"Bert score medio per intent e per shot:\n {avg_intent_shot}")
    
    #print(avg_bert, avg_gen_time, avg_shot, avg_intent)   
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default ="generated.csv")   
    parser.add_argument("-o", "--output", default ="eval.csv")     
    args = parser.parse_args()
    
    df = eval(args.input, args.output)
    summarize(df)
    
