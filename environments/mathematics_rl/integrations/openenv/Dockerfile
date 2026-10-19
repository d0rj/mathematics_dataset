FROM python:3.13.14-slim@sha256:9662417aace5ae7b8e2609cce472b72a8958e134ba372808abe9cc1a0c0125e6
ENV PATH=/opt/mathematics/.venv/bin:$PATH
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
WORKDIR /opt/mathematics
RUN pip install --no-cache-dir uv==0.11.23
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --extra openenv --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --extra openenv
EXPOSE 8000
CMD ["mathematics-openenv", "--host", "0.0.0.0", "--port", "8000"]
