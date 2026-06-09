FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# data.json will live on the persistent volume at /data
# We point DB_FILE there via ENV so the bot survives restarts
ENV DB_FILE=/data/data.json

CMD ["python", "bot.py"]
