# syntax=docker/dockerfile:1.19

# Builder image with uv from the official distroless Docker image
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /bin/

# Set environment variables:
# PYTHONOPTIMIZE — remove 'assert' and '__debug__' at bytecode compilation
# UV_COMPILE_BYTECODE — enable bytecode compilation
# UV_PROJECT_ENVIRONMENT — use system interpreter as environment
# UV_LINK_MODE — copy from the cache instead of linking since it's a mounted volume
# UV_LOCKED — assert that the uv.lock file is up-to-date to pyproject.toml
# UV_NO_DEV — omit development dependencies
# UV_NO_EDITABLE —
ENV PYTHONOPTIMIZE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy
ENV UV_LOCKED=1
ENV UV_NO_DEV=1
ENV UV_NO_EDITABLE=1

# Project path
WORKDIR /app_project

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY --exclude=tests src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync


# Run image
FROM python:3.13-slim AS runner

# Select target app name
ARG app_name=auth

# For python apps SIGINT is more prefferable, not all frameworks correctly handling SIGTERM
STOPSIGNAL SIGINT

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# Use the non-root user to run our application
USER nonroot


# Set environment variables:
# PATH — place app in the environment at the front of the path
# PYTHONOPTIMIZE — use compiled files from `__pycache__` with suffix `opt-1`
# PYTHONFAULTHANDLER — installs error handler for additional signals
# PYTHONUNBUFFERED — avoid logs missing if app crashes due to buffering
ENV PATH=/app:$PATH \
    PYTHONOPTIMIZE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

# Copy only installed Python packages and app code from base stage
# Ensures a clean image without build tools or source cache
COPY --from=builder --chown=nonroot:nonroot usr/local/ usr/local/
COPY --from=builder --chown=nonroot:nonroot app_project/src/$app_name/ app/

# App path
WORKDIR /app

# Add app env file
COPY .env .env

# Run the application
CMD ["python", "main.py"]