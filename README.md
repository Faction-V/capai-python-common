# Capitol AI shared python dependencies

This python package can be included in any python project and includes common
dependencies shared across all services.

- sentry.io integration
  - sentry_message() util
  - setup_sentry() - supports both FastAPI and AWS Lambda environments
- opentelemetry setup for Coralogix ingestion
- fastapi utility routes
  - /health
  - ping_sentry

## Installation

This package can be installed directly from GitHub using Poetry:

```bash
# Add the dependency to your project
poetry add git+https://github.com/Faction-V/capai-python-common.git@v0.1.0
```

Or specify it in your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
capai-python-common = { git = "https://github.com/Faction-V/capai-python-common.git", tag = "v0.1.0" }
```

### Installation Options

There are several ways to reference this package:

#### By Tag (Recommended)
```toml
# Specific version tag (recommended for stability)
capai-python-common = { git = "https://github.com/Faction-V/capai-python-common.git", tag = "v0.1.0" }
```

#### By Branch
```toml
# Latest version from a specific branch
capai-python-common = { git = "https://github.com/Faction-V/capai-python-common.git", branch = "main" }
```

#### By Commit
```toml
# Specific commit
capai-python-common = { git = "https://github.com/Faction-V/capai-python-common.git", rev = "commit-hash" }
```

### For pip/requirements.txt

If you're using pip instead of Poetry:

```
git+https://github.com/Faction-V/capai-python-common.git@v0.1.0
```

### Updating the Package

To update to a newer version:

1. In Poetry projects:
   ```bash
   poetry add git+https://github.com/Faction-V/capai-python-common.git@v0.2.0
   ```
   
2. Or manually update the tag in your `pyproject.toml` and run:
   ```bash
   poetry update capai-python-common
   ```

## Usage

### Sentry Integration

The package provides Sentry integration that works with both FastAPI applications and AWS Lambda functions with automatic environment detection:

```python
# Simple usage - automatically detects if running in FastAPI or AWS Lambda
from capai_python_common import setup_sentry
setup_sentry()  # Auto-detects environment

# Manual override if needed
from capai_python_common import setup_sentry
setup_sentry(flavor="lambda")  # Force Lambda integration
setup_sentry(flavor="fastapi")  # Force FastAPI integration

# Using sentry_message (also auto-detects environment)
from capai_python_common import sentry_message
sentry_message("My message")
```

The environment detection checks for the presence of `AWS_LAMBDA_FUNCTION_NAME` environment variable to determine if running in a Lambda function.

## Release Workflow

For maintainers of this package, follow this workflow when releasing new versions:

1. Update the code with your changes
2. Update the version in `pyproject.toml`
3. Commit the changes:
   ```bash
   git add .
   git commit -m "Description of changes"
   ```
4. Create a new tag matching the version:
   ```bash
   git tag v0.x.y
   ```
5. Push both the changes and the tag:
   ```bash
   git push origin main
   git push origin v0.x.y
   ```

Projects depending on this package can then update to the new version by updating their dependency reference to the new tag.