import json

from flask import Flask, Response, request

from inference import model_fn, input_fn, output_fn, predict_fn


app = Flask(__name__)
model = model_fn("/opt/program")


@app.get("/ping")
def ping():
    """Return HTTP 200 when the serving process has loaded its model."""
    return Response(status=200)


@app.post("/invocations")
def invocations():
    """Decode a JSON candle request, predict with the loaded estimator and return the serialized forecast."""
    payload = input_fn(request.get_data(as_text=True), request.content_type)
    prediction = predict_fn(payload, model)
    body, content_type = output_fn(prediction, "application/json")
    return Response(body, status=200, content_type=content_type)
