from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Real-Estate-AVM")


class PredictionRequest(BaseModel):
    square_footage: float
    bedrooms: int
    bathrooms: float
    latitude: float
    longitude: float


class PredictionResponse(BaseModel):
    predicted_price: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    raise NotImplementedError("Model not trained yet")
