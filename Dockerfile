FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quicknotes.py .
COPY config/prompt.txt config/list_lookup_prompt.txt config/settings.json config/
CMD ["python", "quicknotes.py"]
