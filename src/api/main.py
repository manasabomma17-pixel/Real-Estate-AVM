from fastapi import FastAPI
from src.api.schemas import PredictionRequest, PredictionResponse

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    # no real model trained yet, just sending back a placeholder for now
    return PredictionResponse(predicted_price=0.0, model_version="not trained yet")
