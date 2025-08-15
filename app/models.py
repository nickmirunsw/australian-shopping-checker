from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any


class ProductResult(BaseModel):
    name: str
    price: Optional[float] = None
    was: Optional[float] = None
    promoText: Optional[str] = None
    promoFlag: Optional[bool] = None
    url: Optional[str] = None
    inStock: Optional[bool] = None
    retailer: Literal["woolworths", "coles"]
    display_name: Optional[str] = None  # Clean name for display (without stockcode)
    stockcode: Optional[str] = None  # Store stockcode for absolute uniqueness


class CheckItemsRequest(BaseModel):
    items: str = Field(..., description="Comma-separated list of items to search for")
    postcode: str = Field(..., description="Australian postcode for location-based search")


class AlternativeProduct(BaseModel):
    name: str
    price: Optional[float] = None
    was: Optional[float] = None
    onSale: bool = False
    promoText: Optional[str] = None
    url: Optional[str] = None
    matchScore: Optional[float] = None


class PotentialSaving(BaseModel):
    alternative: str
    currentPrice: float
    alternativePrice: float
    savings: float
    percentage: float


class ItemCheckResult(BaseModel):
    input: str = Field(..., description="Original search term")
    retailer: Literal["woolworths", "coles"]
    bestMatch: Optional[str] = Field(None, description="Name of the best matching product")
    alternatives: List[AlternativeProduct] = Field(default_factory=list, description="Alternative product options")
    onSale: bool = Field(False, description="Whether the product is on sale")
    price: Optional[float] = Field(None, description="Current price")
    was: Optional[float] = Field(None, description="Previous price (if on sale)")
    promoText: Optional[str] = Field(None, description="Promotional text")
    url: Optional[str] = Field(None, description="Product URL")
    inStock: Optional[bool] = Field(None, description="Stock availability")
    potentialSavings: List[PotentialSaving] = Field(default_factory=list, description="Potential savings opportunities")


class CheckItemsResponse(BaseModel):
    results: List[ItemCheckResult]
    postcode: str
    itemsChecked: int


class AdminLoginRequest(BaseModel):
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")


class AdminLoginResponse(BaseModel):
    success: bool
    message: str
    session_token: Optional[str] = None