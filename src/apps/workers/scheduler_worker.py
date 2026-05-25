import os
import time
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.observability.logger import configure_json_logging, set_correlation_id
from src.infrastructure.redis.queue import RedisSchedulerQueue
from src.infrastructure.database.repositories import SqlAlchemyNotificationRepository, SqlAlchemyUnitOfWork
from src.use_cases.process_scheduled_notification import ProcessScheduledNotificationUseCase
from src.use_cases.bootstrap_scheduler import BootstrapSchedulerUseCase


configure_json_logging()
logger = logging.getLogger(__name__)


def run_scheduler():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Instantiate Scheduler Queue
    queue = RedisSchedulerQueue(redis_url)
    
    logger.info("Running Disaster Recovery Bootstrapper...")
    with SessionLocal() as session:
        repo = SqlAlchemyNotificationRepository(session)
        bootstrapper = BootstrapSchedulerUseCase(repo, queue)
        restored_count = bootstrapper.execute()
        logger.info(f"Successfully bootstrapped {restored_count} notifications into Redis.")

    logger.info("Starting Scheduler Daemon...")

    while True:
        try:
            current_time = time.time()
            notification_id_str = queue.pop_due_item(current_time)

            if not notification_id_str:
                time.sleep(0.5)
                continue

            correlation_id = f"sched-{notification_id_str}-{int(current_time)}"
            set_correlation_id(correlation_id)
            
            with SessionLocal() as session:
                repo = SqlAlchemyNotificationRepository(session)
                uow = SqlAlchemyUnitOfWork(session, repo)
                use_case = ProcessScheduledNotificationUseCase(repo, uow, queue)
                
                success = use_case.execute(notification_id_str, correlation_id)
                
                if success:
                    logger.info(f"Successfully processed scheduled notification {notification_id_str}")

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_scheduler()
