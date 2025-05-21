from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from config import LLM
from typing import Optional
import traceback

app = FastAPI()
model = LLM()

class NLGRequest(BaseModel):
    intent: Optional[str] = None
    utterance: Optional[str] = None
    energy_data: Optional[str] = None

class NLGResponse(BaseModel):
    text: str

STATIC_RESPONSES = {
    "greet": "Ciao, in cosa posso esserti utile?",
    "affirm": "Va bene",
    "deny": "Prova a chiedermi qualcos'altro",
    "goodbye": "Va bene. Ciao, alla prossima",
    "nlu_fallback": "Mi dispiace, non ho capito la tua richiesta. Puoi riformularla o chiedermi informazioni sui consumi, produzione o ottimizzazione energetica?"
}

@app.get("/")
def root():
    return {"message": "NLG server is up and running"}

@app.post("/nlg", response_model=NLGResponse)
async def generate_response(payload: NLGRequest):
    print("Ricevuto il payload:", payload)
    try:
        intent = payload.intent
        utterance = payload.utterance
        data = payload.energy_data

        if intent in STATIC_RESPONSES:
            return NLGResponse(text=STATIC_RESPONSES[intent])

        prompt = model.create_prompt(intent, utterance, data)
        response_text = model.inference(prompt)

        return NLGResponse(text=response_text)

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Errore NLG dettagliato:\n{tb_str}")
        raise HTTPException(status_code=500, detail=f"Errore NLG: {str(e)}")



@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"Exception caught:\n{tb_str}")
        raise e  # rilancia l'errore dopo averlo loggato



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
