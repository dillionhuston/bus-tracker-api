from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Tuple
from app.models.Journey import Journey


class PredictionService:
    """
    Service responsible for ETA / status predictions for journeys.
    Uses hybrid approach: official data for bootstrap, user data for accuracy.
    """

    # Configurable defaults
    FALLBACK_DURATION_SECONDS = 30 * 60
    HIGH_DURATION_THRESHOLD_SECONDS = 45 * 60
    MIN_JOURNEYS_FOR_RELIABLE_STATS = 5
    MIN_USER_JOURNEYS_TO_IGNORE_OFFICIAL = 20  # NEW: Threshold to switch

    def predict_journey(
        self,
        db: Session,
        route_id: str,
        start_time: datetime,
    ) -> Tuple[datetime, str]:
        """
        Predict arrival time and status for a journey.
        
        Strategy:
        1. If we have 20+ user journeys, use only those (most accurate)
        2. If we have 5-19 user journeys, blend with official data
        3. If we have <5 user journeys, use official data primarily
        """
        
        # Get user journeys (real crowdsourced data)
        user_journeys = (
            db.query(Journey)
            .filter(
                Journey.route_id == route_id,
                Journey.status == "STOP_REACHED",
                Journey.data_source == "user",  # Only real user data
                Journey.start_time.is_not(None),
                Journey.end_time.is_not(None),
                Journey.end_time > Journey.start_time,
            )
            .order_by(Journey.start_time.desc())
            .limit(100)
            .all()
        )
        
        # Get official/seeded journeys (bootstrap data)
        official_journeys = (
            db.query(Journey)
            .filter(
                Journey.route_id == route_id,
                Journey.status == "STOP_REACHED",
                Journey.data_source == "official",  # Seeded data
                Journey.start_time.is_not(None),
                Journey.end_time.is_not(None),
                Journey.end_time > Journey.start_time,
            )
            .order_by(Journey.start_time.desc())
            .limit(100)
            .all()
        )
        
        user_count = len(user_journeys)
        
        # Phase 1: Enough user data. Use only this
        if user_count >= self.MIN_USER_JOURNEYS_TO_IGNORE_OFFICIAL:
            return self._predict_from_journeys(user_journeys, start_time, "user_data")
        
        # Phase 2: Some user data . Blend with official
        elif user_count >= self.MIN_JOURNEYS_FOR_RELIABLE_STATS:
            combined = user_journeys + official_journeys[:50]  # Prefer user data
            return self._predict_from_journeys(combined, start_time, "blended")
        
        # Phase 3: Bootstrap phase. Use official data
        elif official_journeys:
            return self._predict_from_journeys(official_journeys, start_time, "official_data")
        
        # Phase 4: No data at all. Fallback
        else:
            return (
                start_time + timedelta(seconds=self.FALLBACK_DURATION_SECONDS),
                "unknown",
            )

    def _predict_from_journeys(
        self, 
        journeys: list[Journey], 
        start_time: datetime,
        source: str
    ) -> Tuple[datetime, str]:
        """Helper to calculate prediction from journey list"""
        
        durations_seconds = [
            (j.end_time - j.start_time).total_seconds()
            for j in journeys
            if (j.end_time - j.start_time).total_seconds() > 60
        ]

        if not durations_seconds:
            return (
                start_time + timedelta(seconds=self.FALLBACK_DURATION_SECONDS),
                "unknown",
            )

        avg_duration = sum(durations_seconds) / len(durations_seconds)
        median_duration = sorted(durations_seconds)[len(durations_seconds) // 2]

        predicted_duration = median_duration if len(durations_seconds) >= self.MIN_JOURNEYS_FOR_RELIABLE_STATS else avg_duration
        predicted_arrival = start_time + timedelta(seconds=predicted_duration)

        # Status logic
        status = "on_time"
        if len(durations_seconds) >= self.MIN_JOURNEYS_FOR_RELIABLE_STATS:
            p75 = sorted(durations_seconds)[int(len(durations_seconds) * 0.75)]
            if predicted_duration > p75 * 1.25:
                status = "delayed"
            elif predicted_duration < avg_duration * 0.75:
                status = "early"
        else:
            if predicted_duration > self.HIGH_DURATION_THRESHOLD_SECONDS:
                status = "delayed"

        print(f"[PREDICTION] Using {source}: {len(durations_seconds)} journeys, ETA in {predicted_duration/60:.1f} min")
        
        return predicted_arrival, status