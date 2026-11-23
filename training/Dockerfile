FROM python:3.10-slim
WORKDIR /opt/program
COPY sagemaker/requirements.txt /tmp/inference-requirements.txt
RUN pip install --no-cache-dir -r /tmp/inference-requirements.txt boto3 requests
COPY modeling.py feature_engineering.py historical_backfill.py ./
COPY training/train.py ./
ENTRYPOINT ["python", "train.py"]
