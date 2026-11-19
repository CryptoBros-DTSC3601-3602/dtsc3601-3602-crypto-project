const element = id => document.getElementById(id);
const put = (id, value) => { element(id).textContent = value; };
const percent = value => value == null ? "—" : (100 * value).toFixed(1) + "%";
const date = value => value ? new Intl.DateTimeFormat("en", {
  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC"
}).format(new Date(value)) + " UTC" : "—";
const digest = value => value ? value.slice(0, 19) : "—";
let chartData = [];

function drawChart() {
  if (!chartData.length) return;
  const canvas = element("accuracy-chart");
  const {width, height} = canvas.getBoundingClientRect();
  const scale = devicePixelRatio || 1;
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  ctx.scale(scale, scale);
  const left = 33, right = width - 6, top = 10, bottom = height - 9;
  const x = i => left + (right - left) * i / Math.max(1, chartData.length - 1);
  const y = value => bottom - (bottom - top) * value;
  ctx.font = "10px system-ui";
  ctx.fillStyle = "#645d72";
  ctx.strokeStyle = "#ece7f3";
  for (const value of [0, 0.5, 1]) {
    ctx.fillText(Math.round(value * 100) + "%", 0, y(value) + 3);
    ctx.beginPath();
    ctx.moveTo(left, y(value));
    ctx.lineTo(right, y(value));
    ctx.stroke();
  }
  ctx.beginPath();
  chartData.forEach((value, index) => {
    if (index === 0) ctx.moveTo(x(index), y(value));
    else ctx.lineTo(x(index), y(value));
  });
  ctx.strokeStyle = "#7549d2";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x(chartData.length - 1), y(chartData.at(-1)), 3, 0, 2 * Math.PI);
  ctx.fillStyle = "#7549d2";
  ctx.fill();
}

function render(data) {
  put("freshness", data.sample ? "Sample data" : data.updated_at ? "Updated " + date(data.updated_at) : "Awaiting first update");
  const forecast = data.forecast;
  const labels = {UP: "Up", DOWN: "Down", FLAT: "Flat"};
  element("direction").dataset.direction = forecast?.prediction || "";
  put("direction", labels[forecast?.prediction] || "—");
  put("forecast-time", forecast ? "Forecast issued " + date(forecast.created_at) : "No completed forecast yet");
  for (const label of ["up", "flat", "down"]) {
    const probability = forecast?.probabilities?.[label.toUpperCase()];
    put(label, percent(probability));
    element("bar-" + label).style.width = 100 * (probability ?? 0) + "%";
  }
  put("forecast-model", digest(forecast?.model_digest));
  element("forecast-model").title = forecast?.model_digest || "";
  put("close", forecast?.close == null ? "—" : new Intl.NumberFormat("en", {maximumFractionDigits: 2}).format(forecast.close) + " USDT");
  const outcomes = data.accuracy.outcomes;
  let correct = 0;
  chartData = outcomes.map((outcome, index) => (correct += outcome) / (index + 1));
  put("accuracy-number", percent(chartData.at(-1)));
  const missing = 100 - outcomes.length;
  put("accuracy-detail", outcomes.length
    ? correct + " correct out of " + outcomes.length + " scored" + (missing ? " · " + missing + " more for a full window" : "")
    : "No forecasts have been scored yet");
  element("plot").hidden = !outcomes.length;
  drawChart();

  put("model", digest(data.active_model_digest));
  element("model").title = data.active_model_digest || "";
  const statuses = {reserved: "Reserved", validated: "Validated", failed: "Failed"};
  const rows = data.training_runs.map(run => {
    const tr = document.createElement("tr");
    const values = [run.id, date(run.started_at), statuses[run.status] ?? run.status,
      percent(run.accuracy), run.test_rows ?? "—"];
    for (const [index, value] of values.entries()) {
      const td = tr.insertCell();
      if (index === 2) {
        const badge = document.createElement("span");
        badge.className = "run-status";
        badge.dataset.status = run.status;
        badge.textContent = value;
        td.append(badge);
      } else {
        td.textContent = value;
      }
    }
    return tr;
  });
  element("runs").replaceChildren(...rows);
  element("table-wrap").hidden = !rows.length;
  element("history-empty").hidden = Boolean(rows.length);
  put("history-empty", data.training_configured === false ? "Training history is not configured" : "No retraining runs recorded yet");
}

let lastSnapshot;
async function refresh() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) throw new Error("Dashboard request failed");
    const data = await response.json();
    render(data);
    lastSnapshot = data;
  } catch {
    if (!lastSnapshot) render({forecast: null, accuracy: {outcomes: []}, training_runs: []});
    put("freshness", lastSnapshot?.updated_at
      ? "Update failed · Showing " + date(lastSnapshot.updated_at)
      : "Dashboard temporarily unavailable");
    if (!lastSnapshot) put("history-empty", "Training history is temporarily unavailable");
  }
}
window.addEventListener("resize", drawChart);
refresh();
setInterval(refresh, 5 * 60 * 1000);
