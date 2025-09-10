import os
import logging


def create_logger() -> logging.Logger:
    import sys
    from loguru import logger

    if any(
        [os.environ.get("ENV") == "local", os.environ.get("ENVIRONMENT") == "local"]
    ):
        logger.add(
            sys.stdout,
            colorize=True,
            format="<green>{time}</green> <level>{message}</level>",
        )

    return logger


logger = create_logger()
