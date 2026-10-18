FROM python:3.13-slim
WORKDIR /opt/mathematics
COPY . .
RUN pip install --no-cache-dir '.[openenv]'
EXPOSE 8000
CMD ["mathematics-openenv", "--host", "0.0.0.0", "--port", "8000"]
