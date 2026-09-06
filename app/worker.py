import asyncio
import logging

from app.infrastructure.broker.consumer import run_consumer

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting payment consumer worker...")
    asyncio.run(run_consumer())