from typing import Dict, Any, List
from datetime import datetime, timezone
from app.schemas.price import PriceObservation

class NormalizationService:
    def normalize_market_observation(
        self, raw_data: Dict[Any, Any], query: str, location: str = None
    ) -> List[PriceObservation]:
        observations = []
        shopping_results = raw_data.get("shopping_results", [])
        
        for index, item in enumerate(shopping_results):
            # Extract price logic
            price = item.get("extracted_price")
            if price is None and item.get("price"):
                # fallback for raw price strings if extracted_price is missing but we only want floats
                # a more robust parsing might be needed, but we rely on extracted_price from serpapi
                pass
                
            old_price = item.get("extracted_old_price")
            currency = item.get("currency")
            
            # Name and identifiers
            product_name = item.get("title")
            if not product_name:
                continue
                
            product_id = item.get("product_id")
            merchant = item.get("source")
            rating = item.get("rating")
            reviews = item.get("reviews")
            delivery = item.get("delivery")
            product_link = item.get("link")
            snippet = item.get("snippet")
            
            obs = PriceObservation(
                product_name=product_name,
                product_id=product_id,
                merchant=merchant,
                price=float(price) if price is not None else None,
                old_price=float(old_price) if old_price is not None else None,
                currency=currency,
                rating=float(rating) if rating is not None else None,
                review_count=int(reviews) if reviews is not None else None,
                delivery=delivery,
                product_link=product_link,
                snippet=snippet,
                position=item.get("position", index + 1),
                source="serpapi_google_shopping",
                query=query,
                location=location,
                observed_at=datetime.now(timezone.utc)
            )
            observations.append(obs)
            
        return observations
