import pandas as pd
from bert_score import score
import os
from typing import List

# CONFIG
PROMPT = """Stai supportando un prosumer appartenente a una comunità energetica composta da membri..."""
REFERENCE = """Peer1 ha un surplus di 10.70 kWh. Non ci sono prosumer in deficit, quindi può vendere l'energia ai consumer, in questo ordine:

1. Peer5 (consumer): 5.59 kWh
2. Peer4 (consumer): 0.45 kWh

Il totale venduto è di 6.04 kWh, e il prezzo prezzo consigliato per ogni transazione è di 15 cent/kWh."""


def compute_bertscore(responses: List[str], reference: str):
    references = [reference] * len(responses)
    P, R, F1 = score(responses, references, lang="it")
    return F1.tolist()



def eval(input_path="results.csv", output_path="eval.csv"):
    df = pd.read_csv(input_path)

    # BERTScore
    df["bertscore_f1"] = compute_bertscore(df["risposta"].tolist(), REFERENCE)

    # LLM-as-a-judge
    #...

    # rule-based check
    #...

    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    eval()
