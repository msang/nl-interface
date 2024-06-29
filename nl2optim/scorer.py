import argparse, evaluate, os, random, re
from datasets import Dataset
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, accuracy_score
#from typing import List, Tuple
from utils import *


def parse_constraints(constraint):

    components = re.split(r';\s*', constraint)
    parsed_components = {"variables":[], "values":[], "conditions":[]}
    #parsed_components = []
    for component in components:
        #match = re.match(r'(\w+_t)=(\d+)(?:\sfor\s(.+))?', component)
        match = re.match(r'(\w+_t=\d+)(?:\sfor\s(.+))?', component)
        if match:
            #variable, value, condition = match.groups()
            variable, condition = match.groups()
            #parsed_components.append((variable, value, condition))
            if condition is None:
                condition=""
            parsed_components["variables"].append(variable.rstrip())
            #parsed_components["values"].append(value.rstrip())
            parsed_components["conditions"].append(condition.rstrip())
            
    return parsed_components


def compute_accuracy(model_output, test_set):
    test_parsed = [parse_constraints(c) for c in test_set]
    model_parsed = [parse_constraints(c) for c in model_output]

    test_vars = [test["variables"] for test in test_parsed]
    test_conds = [test["conditions"] for test in test_parsed]
    model_vars = [model["variables"] for model in model_parsed]
    model_conds = [model["conditions"] for model in model_parsed]

    vars_acc=0
    cond_acc=0
    for i, _ in enumerate(zip(test_vars, model_vars, test_conds, model_conds)):
        try:
            vars_acc += accuracy_score(test_vars[i], model_vars[i])
            cond_acc += accuracy_score(test_conds[i], model_conds[i])
            print(test_vars[i], model_vars[i], test_conds[i], model_conds[i])
        except ValueError as e:
            if len(test_vars[i]) > len(model_vars[i]):
                model_vars[i] += ["-"] * (len(test_vars[i]) - len(model_vars[i]))
            else:
                test_vars[i] += ["-"] * (len(model_vars[i]) - len(test_vars[i]))
            if len(test_conds[i]) > len(model_conds[i]):
                model_conds[i] += ["-"] * (len(test_conds[i]) - len(model_conds[i]))
            else:
                test_conds[i] += ["-"] * (len(model_conds[i]) - len(test_conds[i]))
            print(test_vars[i], model_vars[i], test_conds[i], model_conds[i])
            vars_acc += accuracy_score(test_vars[i], model_vars[i])
            cond_acc += accuracy_score(test_conds[i], model_conds[i])

    avg_var_acc = vars_acc/len(test_vars)
    avg_cond_acc = cond_acc/len(test_conds)
    decl_level_acc = (avg_var_acc+avg_cond_acc)/2

    return avg_var_acc, avg_cond_acc, decl_level_acc
    

def compute_gen_metric(model_output, test_set, metric_name, **kwargs):
    """
    Computes a given evaluation metric for model predictions.

    :param model_output (list): List of predictions to score. Each prediction should be a string with tokens separated by spaces.
    :param test_set (list or list[list]): List of references for each prediction or a list of several references per prediction. Each reference should be a string with tokens separated by spaces.
    :param metric_name (str): Name of the metric to compute (e.g., "rouge", "bleu", "chrf").
    :param kwargs: Additional arguments for the metric computation.

    See: https://huggingface.co/spaces/evaluate-metric/{rouge|chrf|bleu|meteor}
    """
    metric = evaluate.load(metric_name)

    if len(model_output) != len(test_set):
        print(f"Computing {metric_name} -- The number of utterances in model output and test set doesn't match!")
        return "!ERR"

    results = []
    for pred, test in zip(model_output, test_set):
        try:
            result = metric.compute(predictions=[pred], references=[test], **kwargs)
            results.append(result)
        except Exception as e:
            print(f"Error computing metric {metric_name} for prediction: {pred} with reference: {test} - {str(e)}")
            return "!ERR"

    return results

def evaluate_constraints(output_file_path, test_file_path):
    data = pd.read_json(test_file_path, lines=True)
    dataset = Dataset.from_pandas(data)
    test = dataset.filter(lambda d: d["split"] == "test" and d["constraint_representation"] != "-")
    test_ir = [" ; ".join(test["constraint_representation"][i]).rstrip("\n") for i in range(len(test["constraint_representation"]))]
    
    with open(output_file_path, "r", encoding="utf-8") as output_file:
        output = [line.rstrip("\n") for line in output_file.readlines()]
    #print(output, test_ir)
    rouge_results = compute_gen_metric(output, test_ir, "rouge")
    bleu_results = compute_gen_metric(output, test_ir, "bleu")
    chrf_results = compute_gen_metric(output, test_ir, "chrf")
    meteor_results = compute_gen_metric(output, test_ir, "meteor")

    if rouge_results == "!ERR" or bleu_results == "!ERR" or chrf_results == "!ERR" or meteor_results == "!ERR":
        return "!ERR", "!ERR", "!ERR", "!ERR"

    rouge = sum([r["rougeL"] for r in rouge_results])/len(rouge_results)
    bleu = sum([b["bleu"] for b in bleu_results])/len(bleu_results)
    chrf = sum([c["score"] for c in chrf_results])/len(chrf_results)
    meteor = sum([c["meteor"] for c in meteor_results])/len(chrf_results)
    #print(rouge, bleu, chrf, meteor)
    #"""
    var, cond, dec_level_accuracy = compute_accuracy(output, test_ir)
    print(f'Declaration-level accuracy: {dec_level_accuracy:.4f}')
    #"""
    return rouge, bleu, chrf, meteor, var, cond, dec_level_accuracy

def write_results(jsonl_file_path, outfile, dir_path):
    out_file_path = os.path.join(dir_path, outfile)
    
    with open(out_file_path, "w", encoding="utf-8") as out:
        out.write("FILE\tChrF\t VAR.ACCURACY \t COND.ACCURACY \t AVG.ACCURACY\n")
        for f in os.listdir(dir_path):
            file_path = os.path.join(dir_path, f)
            if os.path.isfile(file_path) and file_path.startswith(os.path.join(dir_path, "out")):
                print(f"Evaluating output in {file_path}")
                rouge, bleu, chrf, meteor, var, cond, avg_accuracy = evaluate_constraints(file_path, jsonl_file_path)
                f = f.lstrip("out_").rstrip(".txt")
                out.write(f"{f}\t{chrf:.4f}\t {var:.4f} \t{cond:.4f} \t{avg_accuracy:.4f}\n")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--pred_dir_path", default="v2", help="path of the directory containing predicition files")
    parser.add_argument("-g", "--gt_file_name", default="nlu.jsonl", help="Ground truth file path")
    parser.add_argument("-o", "--output_file_name", default="results.txt", help="File with all results")
    args = parser.parse_args()
    write_results(args.gt_file_name, args.output_file_name, args.pred_dir_path)

    