FROM python:3.14-alpine

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /AuthServiceDocker

# Install the application dependencies.
WORKDIR /AuthServiceDocker

RUN uv sync --frozen --no-cache
