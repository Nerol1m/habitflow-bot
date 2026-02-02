from celery import Celery
import os

celery_app = Celery(
    'habits',
    broker='memory://' if os.getenv('USE_REDIS_STUB') == 'true'
            else os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
)

if os.getenv('USE_REDIS_STUB') == 'true':
    celery_app.conf.task_always_eager = True
