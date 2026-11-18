FROM python:3.10-slim

WORKDIR /opt/program

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY inference.py .
COPY btcusdt_direction_15m_60m.joblib .
COPY serve .
RUN chmod +x serve

ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/program:${PATH}"
EXPOSE 8080

CMD ["serve"]
