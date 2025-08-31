# Capitol AI shared python dependencies

This python package can be included in any python project and includes common 
dependencies shared across all services.

- sentry.io integration
  - sentry_message() util
  - setup_sentry()
- opentelemetry setup for Coralogix ingestion
- fastapi utility routes
  - /health
  - ping_sentry