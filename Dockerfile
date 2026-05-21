FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY quicknotes.py entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY config/prompt.txt config/list_lookup_prompt.txt config/settings.json config/
ENTRYPOINT ["./entrypoint.sh"]
