FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY econet24_client.py .
COPY econet24_mqtt_bridge.py .

CMD ["python", "-u", "econet24_mqtt_bridge.py"]
