FROM python:3.10-slim
WORKDIR /opt/program
COPY sagemaker/requirements.txt /tmp/inference-requirements.txt
RUN pip install --no-cache-dir -r /tmp/inference-requirements.txt boto3 requests
COPY cryptobros/ ./cryptobros/
COPY training/train.py ./
ENTRYPOINT ["python", "train.py"]
