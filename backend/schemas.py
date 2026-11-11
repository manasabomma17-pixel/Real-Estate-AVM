from pydantic import BaseModel, Field, model_validator


class PredictionRequest(BaseModel):
    # Field(...) sets the allowed range. FastAPI rejects anything outside it
    # with a 422 error before our code runs, so the model never sees nonsense
    location: str = Field(min_length=1)
    size_sqft: float = Field(gt=0, le=100000)
    bedrooms: int = Field(ge=1, le=20)
    bathrooms: float = Field(ge=0, le=20)
    asking_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_size_per_bedroom(self):
        # the cleaning step removed listings with under 200 sqft per bedroom
        # as unrealistic, so the API refuses them too
        if self.size_sqft / self.bedrooms < 200:
            raise ValueError("size_sqft must be at least 200 sqft per bedroom")
        return self


# one line of the "why this price" breakdown
class PriceFactor(BaseModel):
    name: str
    effect: float  # in Lakhs, positive pushes the price up


class PredictionResponse(BaseModel):
    predicted_price: float           # best estimate, in Lakhs
    price_low: float                 # estimate minus the model's average % error
    price_high: float                # estimate plus the model's average % error
    error_percent: float             # the measured average % error (MAPE)
    price_per_sqft: float            # estimate per sqft, in rupees
    model_version: str
    verdict: str | None = None
    difference_percent: float | None = None
    base_price: float | None = None  # the average prediction, where SHAP starts
    factors: list[PriceFactor] = []
    warnings: list[str] = []         # e.g. size outside what the model has seen
