from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.market_observation import MarketObservation
from app.schemas.price import PriceObservation

class IntelligenceService:
    def compare_prices(self, previous_price: float, current_price: float) -> Dict[str, Any]:
        if previous_price is None or current_price is None:
            return {
                "change_type": "unknown",
                "previous_price": previous_price,
                "current_price": current_price,
                "absolute_change": None,
                "percentage_change": None
            }

        absolute_change = current_price - previous_price
        if previous_price > 0:
            percentage_change = (absolute_change / previous_price) * 100
        else:
            percentage_change = 0.0

        if absolute_change > 0:
            change_type = "price_increase"
        elif absolute_change < 0:
            change_type = "price_decrease"
        else:
            change_type = "no_change"

        return {
            "change_type": change_type,
            "previous_price": previous_price,
            "current_price": current_price,
            "absolute_change": round(absolute_change, 2),
            "percentage_change": round(percentage_change, 2)
        }

    def save_observations(self, db: Session, observations: List[PriceObservation]):
        for obs in observations:
            db_obs = MarketObservation(
                product_id=obs.product_id,
                product_name=obs.product_name,
                merchant_name=obs.merchant,
                query=obs.query,
                price=obs.price,
                old_price=obs.old_price,
                currency=obs.currency,
                rating=obs.rating,
                review_count=obs.review_count,
                availability_signal=obs.delivery,
                product_link=obs.product_link,
                snippet=obs.snippet,
                position=obs.position,
                source=obs.source,
                location=obs.location,
                observed_at=obs.observed_at
            )
            db.add(db_obs)
        db.commit()

    def get_history(self, db: Session, product_name: str) -> List[MarketObservation]:
        return db.query(MarketObservation).filter(
            MarketObservation.product_name == product_name
        ).order_by(desc(MarketObservation.observed_at)).all()

    def get_changes(self, db: Session, product_name: str) -> Dict[str, Any]:
        history = self.get_history(db, product_name)
        if not history:
            return {"status": "insufficient_data"}

        # A change is only meaningful at one merchant: comparing the newest
        # two rows regardless of seller reported one shop's price against
        # another's as a "price change".
        current = history[0]
        previous = next((h for h in history[1:]
                         if h.merchant_name == current.merchant_name), None)
        if previous is None:
            return {"status": "insufficient_data"}

        comparison = self.compare_prices(previous.price, current.price)
        return {
            "product_name": product_name,
            "merchant": current.merchant_name,
            "comparison": comparison,
            "current_observation_date": current.observed_at,
            "previous_observation_date": previous.observed_at
        }
