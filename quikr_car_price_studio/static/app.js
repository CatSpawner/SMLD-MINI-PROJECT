"use strict";

const $ = (id) => document.getElementById(id);
let summary = null;
const money = (value) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 0
}).format(Number.isFinite(Number(value)) ? Number(value) : 0);

function notify(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => toast.classList.remove("show"), 3000);
}

function fillSelect(id, items, preferred) {
  const select = $(id);
  select.replaceChildren();
  items.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  if (preferred && items.includes(preferred)) select.value = preferred;
}

function drawBars(id, values, formatter = (value) => value) {
  const container = $(id);
  container.replaceChildren();
  const entries = Object.entries(values || {});
  const max = Math.max(1, ...entries.map(([, value]) => Number(value) || 0));

  entries.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "hbar-row";

    const name = document.createElement("span");
    name.className = "hbar-label";
    name.title = label;
    name.textContent = label;

    const track = document.createElement("div");
    track.className = "hbar-track";
    track.setAttribute("aria-label", `${label}: ${value}`);

    const fill = document.createElement("div");
    fill.className = "hbar-fill";
    fill.style.width = `${Math.max(1, (Number(value) || 0) / max * 100)}%`;
    track.appendChild(fill);

    const amount = document.createElement("span");
    amount.className = "hbar-value";
    amount.textContent = formatter(value);

    row.append(name, track, amount);
    container.appendChild(row);
  });
}

function drawYear(items) {
  const container = $("year-chart");
  container.replaceChildren();
  const data = (items || []).slice(-22);
  const max = Math.max(1, ...data.map((item) => Number(item.price) || 0));

  data.forEach(({ year, price }) => {
    const column = document.createElement("div");
    column.className = "year-col";

    const bar = document.createElement("div");
    bar.className = "year-bar";
    bar.title = `${year}: ${money(price)}`;
    bar.style.height = `${Math.max(4, (Number(price) || 0) / max * 100)}%`;

    const label = document.createElement("span");
    label.className = "year-label";
    label.textContent = year;

    column.append(bar, label);
    container.appendChild(column);
  });
}

function renderMissing(missing, totalRows) {
  const container = $("missing-chart");
  container.replaceChildren();
  Object.entries(missing || {}).forEach(([name, count]) => {
    const row = document.createElement("div");
    row.className = "quality-row";

    const label = document.createElement("span");
    label.textContent = name;

    const track = document.createElement("div");
    track.className = "quality-track";
    const fill = document.createElement("div");
    fill.className = "quality-fill";
    fill.style.width = `${totalRows ? Math.min(100, count / totalRows * 100) : 0}%`;
    track.appendChild(fill);

    const amount = document.createElement("b");
    amount.textContent = Number(count).toLocaleString("en-IN");
    row.append(label, track, amount);
    container.appendChild(row);
  });
}

function renderSummary(data) {
  summary = data;
  $("total").textContent = data.total_rows.toLocaleString("en-IN");
  $("usable").textContent = data.usable_rows.toLocaleString("en-IN");
  $("median").textContent = money(data.median_price);
  $("duplicates").textContent = data.duplicates.toLocaleString("en-IN");

  drawBars("price-chart", data.price_bins);
  drawBars("fuel-chart", data.fuel_counts);
  drawYear(data.year_medians);
  drawBars("company-chart", data.company_counts);
  renderMissing(data.missing, data.total_rows);

  $("quality-summary").textContent =
    `${data.excluded_rows} rows excluded from modelling because price, year, or kilometres were not usable (including non-numeric “Ask For Price” entries). The original CSV has ${data.columns.length} columns.`;

  fillSelect("car-name", data.names, "Hyundai Santro Xing XO eRLX Euro III");
  fillSelect("company", data.companies, "Hyundai");
  fillSelect("fuel", data.fuels, "Petrol");
  $("year").min = Math.min(1995, data.min_year);
  $("year").max = Math.max(2026, data.max_year);
  $("year").value = Math.min(Number($("year").max), Math.max(Number($("year").min), 2016));
  $("year-out").textContent = $("year").value;
}

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-tab]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-current", active ? "page" : "false");
    });
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.toggle("active", tab.id === button.dataset.tab);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});

$("year").addEventListener("input", () => {
  $("year-out").textContent = $("year").value;
});
$("kms").addEventListener("input", () => {
  $("kms-out").textContent = `${Number($("kms").value).toLocaleString("en-IN")} km`;
});
$("split").addEventListener("input", () => {
  $("split-out").textContent = `${$("split").value}%`;
});

$("car-name").addEventListener("change", () => {
  if (!summary) return;
  const selectedName = $("car-name").value.toLowerCase();
  const matchingCompany = summary.companies
    .slice()
    .sort((a, b) => b.length - a.length)
    .find((company) => selectedName.startsWith(company.toLowerCase()));
  if (matchingCompany) $("company").value = matchingCompany;
});

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an unexpected response. Please restart the app and try again.");
  }
  if (!response.ok) throw new Error(payload.error || "Something went wrong. Please try again.");
  return payload;
}

async function evaluate(showNotice = false) {
  const button = $("eval-form").querySelector("button");
  button.disabled = true;
  button.textContent = "Training models…";

  try {
    const data = await requestJson("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: $("model").value,
        test_size: Number($("split").value) / 100,
        seed: Number($("seed").value)
      })
    });

    const metrics = data.selected;
    $("mae").textContent = money(metrics.mae);
    $("rmse").textContent = money(metrics.rmse);
    $("r2").textContent = metrics.r2.toFixed(3);
    $("train-count").textContent = `Training rows: ${metrics.train_rows.toLocaleString("en-IN")}`;
    $("test-count").textContent = `Test rows: ${metrics.test_rows.toLocaleString("en-IN")}`;
    $("eval-badge").textContent = `${metrics.model.toUpperCase()} · ${Math.round(metrics.test_size * 100)}% TEST`;

    const sorted = data.comparison.filter((item) => !item.error).sort((a, b) => a.mae - b.mae);
    const bestModel = sorted[0]?.model;
    const body = $("comparison-body");
    body.replaceChildren();

    sorted.forEach((item) => {
      const row = document.createElement("tr");
      if (item.model === bestModel) row.className = "best-row";
      [item.model, money(item.mae), money(item.rmse), item.r2.toFixed(3)].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      const readout = document.createElement("td");
      if (item.model === bestModel) {
        const pill = document.createElement("span");
        pill.className = "result-pill";
        pill.textContent = "Lowest MAE";
        readout.appendChild(pill);
      } else {
        readout.textContent = "—";
      }
      row.appendChild(readout);
      body.appendChild(row);
    });

    if (showNotice) notify("Training complete — selected model updated.");
  } catch (error) {
    notify(error.message || "Model training failed.");
  } finally {
    button.disabled = false;
    button.innerHTML = 'Train & compare models <span>↗</span>';
  }
}

$("eval-form").addEventListener("submit", (event) => {
  event.preventDefault();
  evaluate(true);
});

$("predict-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("predict-form").querySelector("button");
  button.disabled = true;
  button.textContent = "Calculating estimate…";

  try {
    const data = await requestJson("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("car-name").value,
        company: $("company").value,
        fuel_type: $("fuel").value,
        year: Number($("year").value),
        kms: Number($("kms").value)
      })
    });

    $("estimate-empty").hidden = true;
    $("estimate-result").hidden = false;
    $("price").textContent = money(data.price);
    $("range").textContent = `${money(data.low)} – ${money(data.high)}`;
    $("active-model").textContent = data.model;
    notify("Estimate calculated.");
  } catch (error) {
    notify(error.message || "Prediction failed.");
  } finally {
    button.disabled = false;
    button.innerHTML = 'Calculate estimate <span>↗</span>';
  }
});

(async function initialize() {
  try {
    const data = await requestJson("/api/summary");
    renderSummary(data);
    await evaluate(false);
  } catch (error) {
    notify("Could not load the dataset. Check the CSV file and restart the app.");
    console.error(error);
  }
})();
