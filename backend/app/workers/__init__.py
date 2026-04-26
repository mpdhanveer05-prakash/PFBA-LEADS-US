from celery import Celery
from app.config import settings

celery_app = Celery(
    "pathfinder",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.scraper_tasks",
        "app.workers.scoring_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
