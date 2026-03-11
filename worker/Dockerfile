FROM python:3.12-slim
WORKDIR /app
COPY checker_core/ ./checker_core/
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
