"""
Common sentry_setup and sentry_message utils
"""

import os
import json
from typing import Optional


def setup_sentry(sentry_dsn: Optional[str] = None, release: str = None):
    """
    Setup sentry.io integration
    docs: https://docs.sentry.io/platforms/python/integrations/fastapi/
    """
    import sentry_sdk
    from sentry_sdk.integrations.typer import TyperIntegration
    from sentry_sdk.integrations.openai import OpenAIIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    if not os.environ.get("SENTRY_DSN", None) and not sentry_dsn:
        return
    sentry_sdk.init(
        dsn=sentry_dsn or os.environ.get("SENTRY_DSN"),
        environment=os.environ.get("ENVIRONMENT", "local"),
        send_default_pii=True,
        instrumenter="otel",  # OpenTelemetry instrumentation
        traces_sample_rate=os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 1.0),
        profile_session_sample_rate=os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", 1.0),
        release=release or os.getenv("IMAGE_TAG", None),
        enable_logs=True,
        profile_lifecycle="trace",
        integrations=[
            OpenAIIntegration(),
            TyperIntegration(),
            FastApiIntegration(
                transaction_style="endpoint",
            ),
            StarletteIntegration(
                transaction_style="endpoint",
            ),
        ],
    )


def sentry_message(
    message: str,
    extra_context: Optional[dict] = None,
    tags: Optional[dict] = None,
    attachments: Optional[list[dict]] = None,
):
    """
    https://docs.sentry.io/error-reporting/capturing/?platform=python#capturing-messages
    Send a detailed message to sentry.io with an optional attachment.
    :param message: (str)
    :param extra_context: (dict) Extra context to send to Sentry.
    :param tags: (dict) Tags to send to Sentry.
    :param attachments: list of dictionaries with keys: data (dict), filename (str), content_type (str)
    :return: hash response from Sentry or None

    Usage:
    from utils import sentry_message
    sentry_message("my special message",
        tags={["foo":"bar"]},
        extra_context={"user": "freddy"},
        attachments=[{"data": {"foo": "bar"}, "filename": "attachment.json", "content_type": "application/json"}]
        )
    """

    import sentry_sdk
    from sentry_sdk.client import NonRecordingClient

    scope = sentry_sdk.get_current_scope()

    # only init if not already initialized
    if isinstance(sentry_sdk.api.get_client(), NonRecordingClient):
        setup_sentry()

    if extra_context:
        for k, v in extra_context.items():
            sentry_sdk.set_context(k, {k: v})
    sentry_sdk.set_tag("category", "observations")  # for filtering in sentry
    sentry_sdk.set_tag("handled", True)
    if tags:
        for k, v in tags.items():
            sentry_sdk.set_tag(k, v)

    # Attach JSON payloads to the Sentry message
    if attachments:
        for attachment in attachments:
            data = attachment.get("data", {})
            if not data:
                continue
            json_data = json.dumps(data, indent=2).encode("utf-8")
            scope.add_attachment(
                bytes=json_data,
                filename=attachment.get("filename", "attachment.json"),
                content_type=attachment.get("content_type", "application/json"),
            )

    return sentry_sdk.capture_message(message)
