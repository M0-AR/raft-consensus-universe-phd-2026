FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /raft
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY experiments/ ./experiments/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
RUN mkdir -p results
CMD ["python3", "scripts/run_all.py"]
