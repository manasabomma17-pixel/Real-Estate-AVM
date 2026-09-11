from pydantic import BaseModel, Field


class PropertyFeatures(BaseModel):
    size_sqft: float
    bedrooms: int
    bathrooms: float
    age_years: float
    lot_size_sqft: float | None = None


class LocationFeatures(BaseModel):
    distance_to_school_km: float
    distance_to_hospital_km: float
    distance_to_transit_km: float
    distance_to_city_center_km: float


class MacroFeatures(BaseModel):
    regional_hpi: float | None = None
    mortgage_rate_pct: float | None = None
    cpi_index: float | None = None


class PredictionRequest(BaseModel):
    property: PropertyFeatures
    location: LocationFeatures
    macro: MacroFeatures | None = None


class PredictionResponse(BaseModel):
    predicted_price: float
    prediction_interval_low: float | None = Field(default=None)
    prediction_interval_high: float | None = Field(default=None)
    model_version: str
