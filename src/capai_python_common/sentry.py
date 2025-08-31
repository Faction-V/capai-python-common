"""
Common sentry_setup and sentry_message utils
"""

import os
import json
from typing import Optional


def setup_sentry(sentry_dsn: Optional[str] = None, release: str = None, flavor: Optional[str] = None):
    """
    Setup sentry.io integration with automatic environment detection
    
    :param sentry_dsn: Optional Sentry DSN. If not provided, will use SENTRY_DSN environment variable
    :param release: Optional release version. If not provided, will use IMAGE_TAG environment variable
    :param flavor: Optional override for environment detection ("fastapi" or "lambda").
                  If not provided, will auto-detect based on environment variables
    
    docs:
    - FastAPI: https://docs.sentry.io/platforms/python/integrations/fastapi/
    - AWS Lambda: https://docs.sentry.io/platforms/python/integrations/aws-lambda/
    """
    import sentry_sdk
    from sentry_sdk.integrations.typer import TyperIntegration
    from sentry_sdk.integrations.openai import OpenAIIntegration
    
    # Auto-detect environment if flavor is not specified
    if flavor is None:
        # Check if running in AWS Lambda
        is_lambda = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
        detected_flavor = "lambda" if is_lambda else "fastapi"
        flavor = detected_flavor
    
    # Common integrations
    integrations = [
        OpenAIIntegration(),
        TyperIntegration(),
    ]
    
    # Add environment-specific integrations
    if flavor.lower() == "lambda":
        from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
        integrations.append(AwsLambdaIntegration(timeout_warning=True))
    else:  # Default to FastAPI
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        integrations.extend([
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
        ])

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
        integrations=integrations,
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
        # Auto-detection will happen in setup_sentry
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
