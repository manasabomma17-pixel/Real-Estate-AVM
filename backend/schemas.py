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

    # the model learned from 2017-19 listings. these bring its estimate up to
    # today's market with a published-rate factor for the area (or the city)
    today_price: float | None = None
    today_low: float | None = None
    today_high: float | None = None
    today_price_per_sqft: float | None = None
    market_factor: float = 1.0
    market_basis: str = "none"       # "area", "city" or "none"
    market_source: str | None = None


# ----- requests for the helper endpoints the React app uses -----

class ListingText(BaseModel):
    # text copied from a property website, or a link to the listing
    text: str = Field(max_length=20000)


class PlaceQuery(BaseModel):
    # a society, street or landmark, a Google Maps link, or "12.93, 77.69"
    query: str = Field(min_length=1, max_length=2000)
    area: str = Field(min_length=1)  # the area picked in the form, to check the spot is in it


class AdviceRequest(PredictionRequest):
    # the flat's exact spot, if the user found it, so distances are measured from there
    exact_lat: float | None = Field(default=None, ge=-90, le=90)
    exact_lon: float | None = Field(default=None, ge=-180, le=180)
    # the building's age. the model was not trained with it (our data has no
    # age), so it only changes the advice and a separate rough adjustment
    building_age: int | None = Field(default=None, ge=0, le=100)
    under_construction: bool = False
