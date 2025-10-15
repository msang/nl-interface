from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from config import LLM
from typing import Optional, Dict, Any

app = FastAPI()
model = LLM()

"""
class NLGRequest(BaseModel):
    intent: Optional[str] = None
    utterance: Optional[str] = None
    data: Optional[str] = None
"""

class NLGResponse(BaseModel):
    text: str


@app.get("/")
def root():
    return {"message": "NLG server is up and running"}

@app.post("/nlg", response_model=NLGResponse)
async def generate_response(rasa_payload: Dict[str,Any]):

    #print("RASA payload: ",rasa_payload)

    try:    
        tracker = rasa_payload.get("tracker", {})
        if not tracker:
            intent = rasa_payload.get("intent", {})
        else:
            #print("Tracker content:", tracker)    
            intent = tracker.get("latest_message", {}).get("intent", {}).get("name", None)

        STATIC_INTENTS = ("")
        response =""
        STATIC_RESPONSES={"greet":"Ciao, in cosa posso esserti utile?", \
                         "affirm":"Va bene", \
                         "deny": "Prova a chiedermi qualcos'altro", \
                         "goodbye": "Va bene. Ciao, alla prossima", \
                         "nlu_fallback": "Mi dispiace, non ho capito la tua richiesta. Puoi riformularla o chiedermi informazioni sui consumi, produzione o ottimizzazione energetica?"}
        
        if intent not in STATIC_RESPONSES:
            utterance=rasa_payload.get("utterance", {})
            data = rasa_payload.get("energy_data", {})
            
            try:
                prompt = model.create_prompt(intent, utterance, data)
                #print("Prompt generato:", prompt)
                response = model.inference(prompt)
            except Exception as e:
                raise ValueError(f"Errore durante la generazione della risposta da parte del modello: {str(e)}")

        else:
            response = STATIC_RESPONSES[intent]
        
        return NLGResponse(text=response)

    except Exception as e:
        print("Errore nel server NLG:", str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
    
