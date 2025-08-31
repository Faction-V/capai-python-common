"""
Utility routes for platform API health checks and monitoring.
"""

from typing import Dict, Union
from datetime import datetime
from fastapi import APIRouter, status
from pydantic import BaseModel

import sentry_sdk


router = APIRouter(tags=["Utilities"])


class HealthResponse(BaseModel):
    """Standard health check response model."""

    message: str

class SentryResponse(BaseModel):
    """Sentry test response model."""

    sentry_response_hash: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check() -> HealthResponse:
    """
    Simple health check endpoint to verify the service is running.

    Returns:
        HealthResponse: A simple message indicating the service is alive.
    """
    return HealthResponse(message="Service is alive")


@router.get("/ping-sentry", response_model=SentryResponse, status_code=status.HTTP_200_OK)
def ping_sentry() -> Union[SentryResponse, Dict[str, str]]:
    """
    Test Sentry.io connection by generating a test exception.

    Deliberately triggers a division by zero exception and captures it with Sentry,
    returning the event ID hash from Sentry.

    Returns:
        SentryResponse or Dict: Contains the Sentry event ID hash.
        Returns a dictionary when called directly (not through FastAPI).
    """
    try:
        1 / 0
    except Exception as e:
        with sentry_sdk.push_scope() as scope:
            scope.user = {"email": "foobar@gmail.com"}
            scope.set_extra("test", datetime.now().strftime("%m/%d/%Y, %H:%M:%S"))
            scope.level = "warning"
            event_id = sentry_sdk.capture_exception(e)

        # Handle the case when event_id is None
        if event_id is None:
            event_id = "no-event-id-generated"

        # Return a dictionary when called directly (e.g., from CLI)
        # This avoids Pydantic validation issues when called outside of FastAPI
        if "__name__" in globals() and globals()["__name__"] != "__main__":
            return {"sentry_response_hash": event_id}

        # Return a SentryResponse object when called through FastAPI
        return SentryResponse(sentry_response_hash=event_id)



