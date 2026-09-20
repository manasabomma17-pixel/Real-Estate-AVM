from pydantic import BaseModel


class PropertyFeatures(BaseModel):
    size_sqft: float
    bedrooms: int
    bathrooms: float


class LocationFeatures(BaseModel):
    distance_to_school_km: float
    distance_to_hospital_km: float
    distance_to_transit_km: float


class PredictionRequest(BaseModel):
    property: PropertyFeatures
    location: LocationFeatures


class PredictionResponse(BaseModel):
    predicted_price: float
    model_version: str
