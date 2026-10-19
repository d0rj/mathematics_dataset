# syntax=docker/dockerfile:1
FROM docker:29.7.2-cli@sha256:3f4743208d2338c934d7b8bcfbe1bb54c0b2355c510ad5e0f31c0c4a54bd704e AS docker-cli
FROM python:3.13.14-slim@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6
ARG FRAMEWORK
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
ENV PATH=/opt/math/.venv/bin:$PATH
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 CUDA_VISIBLE_DEVICES=""
RUN pip install --no-cache-dir uv==0.11.23
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
WORKDIR /opt/math
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --extra "$FRAMEWORK" --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --extra "$FRAMEWORK"
LABEL org.opencontainers.image.title="Mathematics RL local integration checks"
CMD ["python", "-m", "pytest", "-p", "pytest_asyncio.plugin", "tests", "-q"]
