from typing import Tuple, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.Journey import Journey
from app.utils.logger.logger import get_logger


class PredictionService:
    """
    ETA & status prediction service.

    How it decides what data to trust:
    - 20+ real user journeys → use only user data (most accurate)
    - 5-19 user journeys → blend user + official (prefer user)
    - <5 user journeys → use official timetable (bootstrap)
    - No data → safe fallback (30 min)
    """

    FALLBACK_MINUTES = 30
    HIGH_THRESHOLD_MINUTES = 45
    MIN_FOR_STATS = 5
    MIN_TO_TRUST_USERS_ONLY = 20


    @staticmethod
    def predict_journey(db: Session,route_id: str,start_time: datetime,)-> Tuple[datetime, str]:
        """
        Main prediction method.

        Returns: (predicted_arrival_time, status)
        status: "on_time", "delayed", "early", "unknown"
        """
        logger = get_logger()

        # Safety: very far future → fallback
        now_utc = datetime.now(timezone.utc)
        if start_time > now_utc + timedelta(hours=24):
            logger.warning(f"Very future start time ({start_time}), using fallback")
            return start_time + timedelta(minutes=PredictionService.FALLBACK_MINUTES), "unknown"

        # Get user submitted completed journeys (only durations)
        user_durations = db.query(
            (Journey.end_time - Journey.start_time).label("duration")
        ).filter(
            Journey.route_id == route_id,
            Journey.status == "STOP_REACHED",
            Journey.data_source == "user",
            Journey.start_time.is_not(None),
            Journey.end_time.is_not(None),
            Journey.end_time > Journey.start_time,
            (Journey.end_time - Journey.start_time) > timedelta(minutes=1)
        ).order_by(Journey.start_time.desc()).limit(100).all()

        user_count = len(user_durations)
        logger.debug(f"User journeys found: {user_count}")

        if user_count >= PredictionService.MIN_TO_TRUST_USERS_ONLY:
            durations_sec = [row.duration.total_seconds() for row in user_durations]
            source = "user_only"
        else:
            official_durations = db.query(
                (Journey.end_time - Journey.start_time).label("duration")
            ).filter(
                Journey.route_id == route_id,
                Journey.status == "STOP_REACHED",
                Journey.data_source == "official",
                Journey.start_time.is_not(None),
                Journey.end_time.is_not(None),
                Journey.end_time > Journey.start_time,
                (Journey.end_time - Journey.start_time) > timedelta(minutes=1)
            ).limit(50).all()

            combined = user_durations + official_durations
            durations_sec = [row.duration.total_seconds() for row in combined]
            source = "blended" if user_count > 0 else "official"

        if not durations_sec:
            logger.info(f"No valid durations for route {route_id} → fallback")
            return start_time + timedelta(minutes=PredictionService.FALLBACK_MINUTES), "unknown"

        # Compute stats
        count = len(durations_sec)
        avg_sec = sum(durations_sec) / count
        sorted_sec = sorted(durations_sec)
        median_sec = sorted_sec[count // 2]

        # Median is more robust with enough data
        use_median = count >= PredictionService.MIN_FOR_STATS
        predicted_sec = median_sec if use_median else avg_sec

        predicted_arrival = start_time + timedelta(seconds=predicted_sec)

        # Status logic
        status = "on_time"

        if use_median:
            p75 = sorted_sec[int(count * 0.75)]
            if predicted_sec > p75 * 1.25:
                status = "delayed"
            elif predicted_sec < avg_sec * 0.75:
                status = "early"
        else:
            if predicted_sec > PredictionService.HIGH_THRESHOLD_MINUTES * 60:
                status = "delayed"

        # Log result
        logger.info(
            f"[PREDICTION] {source} | "
            f"{count} journeys | "
            f"ETA +{predicted_sec/60:.1f} min | "
            f"status: {status}"
        )
        return predicted_arrival, status