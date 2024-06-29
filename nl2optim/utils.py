from datasets import Dataset
import pandas as pd
import json


def tsv_to_jsonl(tsv_file_path, jsonl_file_path):

    df = pd.read_csv(tsv_file_path, sep="\t")

    def split_declarations(declaration):
        return [d.strip() for d in declaration.split(";")]

    df["constraint_slot"] = df["constraint_slot"].apply(lambda x: split_declarations(x))
    df["constraint_type"] = df["constraint_type"].apply(lambda x: split_declarations(x))
    df["vars"] = df["vars"].apply(lambda x: split_declarations(x))
    df["var_values"] = df["var_values"].apply(lambda x: split_declarations(x))
    df["params"] = df["params"].apply(lambda x: split_declarations(x))
    df["param_values"] = df["param_values"].apply(lambda x: split_declarations(x))
    df["condition_type"] = df["condition_type"].apply(lambda x: split_declarations(x))
    df["constraint_representation"] = df["constraint_representation"].apply(lambda x: split_declarations(x))

    df.drop("appliance_slot", axis=1)
    
    with open(jsonl_file_path, 'w') as jsonl_file:
        for record in df.to_dict(orient='records'):
            jsonl_file.write(json.dumps(record) + '\n')


def jsonl_to_df(jsonl_file_path):
    """
    :param file_path:
    :return nested list of all declarations, values and constraint IR
    """
    try:
        data = []
        with open(jsonl_file_path, 'r') as jsonl_file:
            for line in jsonl_file:
                data.append(json.loads(line))
    
        df = pd.DataFrame(data)
        return df
        
    except Exception as e:
        print(f"Error while loading the file: {e}")
        return None


def extract_text_and_slots(jsonl_file):
    data = pd.read_json(jsonl_file, lines=True)
    dataset = Dataset.from_pandas(data)
    test = dataset.filter(lambda d: d["split"]=="test" and d["constraint_representation"] != "-")
    for t, s in zip(test["text"], test["constraint_slot"]):
        s = " ; ".join(s) if len(s) > 1 else s
        print(f"Enunciato: \"{t}\" \n Span di testo relativo/i alle preferenze dell'utente: \"{s}\"")
        

def read_from_file(file_path="prompt_base.txt"):
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.read()        
    return file_content


def create_it_data(data_path="nlu.jsonl", jsonl_path="instructions.jsonl"):
    data = pd.read_json(data_path, lines=True)
    dataset = Dataset.from_pandas(data)
    test = dataset.filter(lambda d: d["split"]=="test" and d["constraint_representation"] != "-")
    constraints = test["constraint_slot"]
    constraint_type=test["constraint_type"]
    constraint_repr=test["constraint_representation"]
    labeled_utterances=[]
    
    for i, utterance in enumerate(test["text"]):           
        #print(utterance)
        for c, ctype in zip(constraints[i], constraint_type[i]):
            #print(c, ctype)
            xml_tag = f"<CONSTR_{ctype.upper()}>{c}</CONSTR_{ctype.upper()}>"
            utterance = utterance.replace(c, xml_tag)
        #print(utterance)
        labeled_utterances.append(utterance)
    data={}
    if shot_no == 0:
        #return {"utterances":test["text"]}
        data={"utterances":labeled_utterances, "constraints": constraint_repr}
    else:
        try:
            add_info = read_from_file(add_prompt_file_path)
            data={"utterances":labeled_utterances, "additional_info": [add_info], "constraints": constraint_repr}    
        except:
            print("It seems like you didn't pass a prompt file path. If one or more examples are to be included in the prompt, please put them in a text file and pass the file as argument using the -p flag")
            data={}

    

if __name__ == "__main__":
    tsv_file_path = "nlu.txt"
    jsonl_file_path = "nlu.jsonl"
    
    tsv_to_jsonl(tsv_file_path, jsonl_file_path)
    #extract_text_and_slots(jsonl_file_path)
