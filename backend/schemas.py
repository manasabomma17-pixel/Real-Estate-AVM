from pydantic import BaseModel


class PredictionRequest(BaseModel):
    location: str
    size_sqft: float
    bedrooms: int
    bathrooms: float
    asking_price: float | None = None


class PredictionResponse(BaseModel):
    predicted_price: float
    model_version: str
    verdict: str | None = None
    difference_percent: float | None = None
