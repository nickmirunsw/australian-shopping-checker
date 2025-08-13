from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEFAULT_POSTCODE: str = "2000"
    CACHE_TTL_MIN: int = 10
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Playwright fallback settings
    ENABLE_PLAYWRIGHT_FALLBACK: bool = False
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000  # 30 seconds in milliseconds
    
    # Product matching configuration
    MIN_PRODUCT_SIMILARITY: float = 0.3
    HIGH_CONFIDENCE_THRESHOLD: float = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.6
    EXACT_MATCH_BONUS: float = 0.2
    BRAND_MATCH_BONUS: float = 0.15
    SIZE_MATCH_BONUS: float = 0.1
    KEYWORD_MATCH_BONUS: float = 0.05
    
    class Config:
        env_file = ".env"


settings = Settings()