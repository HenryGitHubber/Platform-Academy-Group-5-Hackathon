/**
 * DASHBOARD.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Fetches processed/all_data.json from S3 (or local), then renders all
 * Chart.js visualisations and populates the KPI summary cards.
 */

// ── Colour palette ─────────────────────────────────────────────────────────
const YEAR_COLOURS = ["#1565C0", "#2E7D32", "#E65100", "#6A1B9A", "#00838F"];
const STREAM_COLOURS = [
  "#1565C0","#2E7D32","#E65100","#6A1B9A","#00838F",
  "#AD1457","#FF8F00","#558B2F","#00695C","#4527A0",
];
const MODULE_COLOURS = ["#1565C0","#2196F3","#4CAF50","#FF9800","#E91E63","#9C27B0"];
const DOUGHNUT_COLOURS = [
  "#1565C0","#2E7D32","#E65100","#6A1B9A","#00838F",
  "#AD1457","#FF8F00","#00695C",
];

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = {
  eur: (n) => `€${Number(n).toLocaleString("en-ZA", { maximumFractionDigits: 0 })}`,
  pct: (n) => `${Number(n).toFixed(1)}%`,
  num: (n) => Number(n).toLocaleString("en-ZA"),
};

function setEl(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function showError(message) {
  const el = document.getElementById("loadingOverlay");
  if (el) {
    el.innerHTML = `<div class="error-state">
      <span class="error-icon">⚠️</span>
      <p>${message}</p>
      <small>Check the browser console for details.</small>
    </div>`;
  }
}

function hideLoading() {
  const el = document.getElementById("loadingOverlay");
  if (el) el.style.display = "none";
}

// ── Chart default options ───────────────────────────────────────────────────
Chart.defaults.font.family = "'Segoe UI', system-ui, -apple-system, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = "#555";
Chart.defaults.plugins.legend.position = "bottom";
Chart.defaults.plugins.tooltip.padding = 10;

const GRID_STYLE = {
  color: "rgba(0,0,0,0.06)",
  drawBorder: false,
};

// ── Chart builders ──────────────────────────────────────────────────────────

function buildYearChart(byYear) {
  const labels = byYear.map((y) => y.year.toString());
  const employees = byYear.map((y) => y.employee_count);
  const costs = byYear.map((y) => y.total_cost_eur);

  new Chart(document.getElementById("yearChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Employees",
          data: employees,
          backgroundColor: YEAR_COLOURS.slice(0, labels.length),
          borderRadius: 6,
          yAxisID: "yEmployees",
        },
        {
          label: "Total Cost (EUR)",
          data: costs,
          type: "line",
          borderColor: "#E65100",
          backgroundColor: "rgba(230,81,0,0.1)",
          borderWidth: 2.5,
          pointRadius: 5,
          pointBackgroundColor: "#E65100",
          fill: true,
          tension: 0.3,
          yAxisID: "yCost",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.dataset.label === "Total Cost (EUR)"
                ? ` ${fmt.eur(ctx.raw)}`
                : ` ${fmt.num(ctx.raw)} employees`,
          },
        },
      },
      scales: {
        yEmployees: {
          type: "linear",
          position: "left",
          grid: GRID_STYLE,
          title: { display: true, text: "Employees" },
          ticks: { stepSize: 20 },
        },
        yCost: {
          type: "linear",
          position: "right",
          grid: { display: false },
          title: { display: true, text: "Cost (EUR)" },
          ticks: { callback: (v) => fmt.eur(v) },
        },
      },
    },
  });
}

function buildSatisfactionChart(byYear) {
  const labels = byYear.map((y) => y.year.toString());

  // Build per-question datasets for key satisfaction questions
  const keyQuestions = [
    { id: "Q1", label: "Overall experience" },
    { id: "Q3", label: "Cloud confidence" },
    { id: "Q7", label: "Would recommend" },
    { id: "Q9", label: "Upskilling sufficiency" },
  ];

  const datasets = keyQuestions.map((q, i) => ({
    label: q.label,
    data: byYear.map((y) => y.avg_by_question?.[q.id] ?? null),
    borderColor: YEAR_COLOURS[i],
    backgroundColor: YEAR_COLOURS[i] + "22",
    borderWidth: 2.5,
    pointRadius: 5,
    tension: 0.3,
    fill: false,
  }));

  // Add overall average as a thicker line
  datasets.unshift({
    label: "Overall avg",
    data: byYear.map((y) => y.avg_satisfaction_overall),
    borderColor: "#212121",
    borderWidth: 3,
    pointRadius: 6,
    borderDash: [6, 3],
    tension: 0.3,
    fill: false,
  });

  new Chart(document.getElementById("satisfactionChart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top" } },
      scales: {
        y: {
          min: 0,
          max: 10,
          grid: GRID_STYLE,
          title: { display: true, text: "Score (1–10)" },
        },
        x: { grid: GRID_STYLE },
      },
    },
  });
}

function buildModuleChart(moduleStats) {
  const moduleLabels = {
    skillbuilder: "Cloud Skillbuilder",
    instructor: "Instructor-Led",
    mytms: "MyTMS",
    game_day: "Game Day",
    hackathon: "Hackathon",
    cert: "Certification",
  };

  const labels = Object.keys(moduleStats).map((k) => moduleLabels[k] || k);
  const signed = Object.values(moduleStats).map((m) => m.signed);
  const completed = Object.values(moduleStats).map((m) => m.completed);
  const rates = Object.values(moduleStats).map((m) => m.completion_rate_pct);

  new Chart(document.getElementById("moduleChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Enrolled",
          data: signed,
          backgroundColor: "rgba(21,101,192,0.25)",
          borderColor: "#1565C0",
          borderWidth: 1.5,
          borderRadius: 4,
        },
        {
          label: "Completed",
          data: completed,
          backgroundColor: "#1565C0",
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              if (ctx.datasetIndex === 1) {
                return `  Completion rate: ${rates[ctx.dataIndex]}%`;
              }
              return "";
            },
          },
        },
      },
      scales: {
        x: {
          grid: GRID_STYLE,
          title: { display: true, text: "Number of participants" },
        },
        y: { grid: { display: false } },
      },
    },
  });
}

function buildStreamChart(byStream) {
  const top8 = byStream.slice(0, 8);
  const labels = top8.map((s) => s.stream);
  const counts = top8.map((s) => s.employee_count);
  const satisfaction = top8.map((s) => s.avg_satisfaction);

  new Chart(document.getElementById("streamChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Employees",
          data: counts,
          backgroundColor: STREAM_COLOURS.slice(0, labels.length),
          borderRadius: 6,
          yAxisID: "yCount",
        },
        {
          label: "Avg Satisfaction",
          data: satisfaction,
          type: "line",
          borderColor: "#E65100",
          backgroundColor: "rgba(230,81,0,0.1)",
          borderWidth: 2.5,
          pointRadius: 5,
          pointBackgroundColor: "#E65100",
          tension: 0.3,
          yAxisID: "ySat",
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top" } },
      scales: {
        yCount: {
          type: "linear",
          position: "bottom",
          title: { display: true, text: "Employees" },
          grid: GRID_STYLE,
        },
        ySat: {
          type: "linear",
          position: "top",
          min: 0,
          max: 10,
          grid: { display: false },
          title: { display: true, text: "Satisfaction (1–10)" },
        },
        y: { grid: { display: false } },
      },
    },
  });
}

function buildQ8Chart(q8Data) {
  // Filter out empty string keys
  const filtered = Object.entries(q8Data).filter(([k]) => k.trim() !== "");
  const labels = filtered.map(([k]) => k);
  const data = filtered.map(([, v]) => v);

  new Chart(document.getElementById("q8Chart"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor: DOUGHNUT_COLOURS, borderWidth: 2, hoverOffset: 8 }],
    },
    options: {
      responsive: true,
      cutout: "60%",
      plugins: {
        legend: { position: "right" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = ((ctx.raw / total) * 100).toFixed(1);
              return ` ${ctx.raw} responses (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function buildQ11Chart(q11Data) {
  const yes = parseInt(q11Data["1"] || 0);
  const no = parseInt(q11Data["0"] || 0);
  const total = yes + no;

  // Update the centre text element
  setEl("q11Yes", yes.toString());
  setEl("q11Pct", total > 0 ? `${((yes / total) * 100).toFixed(0)}%` : "–");

  new Chart(document.getElementById("q11Chart"), {
    type: "doughnut",
    data: {
      labels: ["Yes — prefer Platform Academy", "No — prefer external tools"],
      datasets: [
        {
          data: [yes, no],
          backgroundColor: ["#2E7D32", "#E65100"],
          borderWidth: 2,
          hoverOffset: 8,
        },
      ],
    },
    options: {
      responsive: true,
      cutout: "65%",
      plugins: {
        legend: { position: "right" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const t = ctx.dataset.data.reduce((a, b) => a + b, 0);
              return ` ${ctx.raw} (${((ctx.raw / t) * 100).toFixed(1)}%)`;
            },
          },
        },
      },
    },
  });
}

function buildCostPerStreamChart(byStream) {
  const sorted = [...byStream].sort((a, b) => b.avg_cost_per_employee_eur - a.avg_cost_per_employee_eur);
  const labels = sorted.map((s) => s.stream);
  const costs = sorted.map((s) => s.avg_cost_per_employee_eur);

  new Chart(document.getElementById("costStreamChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Avg Cost per Employee (EUR)",
          data: costs,
          backgroundColor: costs.map((_, i) => STREAM_COLOURS[i % STREAM_COLOURS.length]),
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => ` ${fmt.eur(ctx.raw)}` },
        },
      },
      scales: {
        y: {
          grid: GRID_STYLE,
          title: { display: true, text: "EUR" },
          ticks: { callback: (v) => fmt.eur(v) },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── Summary cards ───────────────────────────────────────────────────────────

function populateSummaryCards(data) {
  const s = data.summary;
  const user = auth.getUser();

  setEl("userEmail", user?.email || "");
  setEl("generatedAt", new Date(data.generated_at).toLocaleString("en-ZA"));
  setEl("cardTotalEmployees", fmt.num(s.total_employees));
  setEl("cardTotalCost", fmt.eur(s.total_cost_eur));
  setEl("cardAvgSatisfaction", `${s.avg_satisfaction_overall} / 10`);
  setEl("cardYears", s.years_available.join(", "));
  setEl("cardAvgCost", fmt.eur(s.total_cost_eur / s.total_employees));
  setEl("cardTopStream", data.by_stream?.[0]?.stream || "—");
  setEl("cardSuccessRate", s.overall_success_rate_pct != null ? `${s.overall_success_rate_pct}%` : "—");
  setEl("cardDataQuality", s.data_quality_pct != null ? `${s.data_quality_pct}%` : "—");
}

// ── NEW: ROI Bubble / Scatter chart ─────────────────────────────────────────
// X = avg cost, Y = avg satisfaction, bubble size = completion rate

function buildROIScatterChart(roiData) {
  const streams = roiData.by_stream;
  const datasets = streams.map((s, i) => ({
    label: s.stream,
    data: [{
      x: s.avg_cost_eur,
      y: s.avg_satisfaction,
      r: Math.max(6, s.avg_completion_pct / 5), // radius scaled from completion %
    }],
    backgroundColor: STREAM_COLOURS[i % STREAM_COLOURS.length] + "BB",
    borderColor: STREAM_COLOURS[i % STREAM_COLOURS.length],
    borderWidth: 1.5,
  }));

  new Chart(document.getElementById("roiScatterChart"), {
    type: "bubble",
    data: { datasets },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const s = streams[ctx.datasetIndex];
              return [
                ` ${s.stream}`,
                ` Cost: ${fmt.eur(s.avg_cost_eur)}/employee`,
                ` Satisfaction: ${s.avg_satisfaction}/10`,
                ` Completion: ${s.avg_completion_pct}%`,
                ` ROI Rank: #${s.rank}`,
              ];
            },
          },
        },
      },
      scales: {
        x: {
          grid: GRID_STYLE,
          title: { display: true, text: "Avg Cost per Employee (EUR)" },
          ticks: { callback: (v) => fmt.eur(v) },
        },
        y: {
          grid: GRID_STYLE,
          min: 5,
          max: 10,
          title: { display: true, text: "Avg Satisfaction Score (1–10)" },
        },
      },
    },
  });
}

// ── NEW: ROI Ranking Table ────────────────────────────────────────────────────

function buildROITable(roiData) {
  const tbody = document.getElementById("roiTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  roiData.by_stream.forEach((s) => {
    const tr = document.createElement("tr");
    const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };
    const medal = medalMap[s.rank] || "";
    tr.innerHTML = `
      <td><strong>${medal} #${s.rank}</strong></td>
      <td>${s.stream}</td>
      <td>${fmt.eur(s.avg_cost_eur)}</td>
      <td>${s.avg_satisfaction}/10</td>
      <td>${s.avg_completion_pct}%</td>
      <td><strong>${s.roi_score.toFixed(3)}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── NEW: Dual-Axis Cost vs Satisfaction Trend ────────────────────────────────

function buildCostSatisfactionTrendChart(byYear) {
  const labels = byYear.map((y) => y.year.toString());
  const costs = byYear.map((y) => y.avg_cost_per_employee_eur);
  const satisfaction = byYear.map((y) => y.avg_satisfaction_overall);

  new Chart(document.getElementById("costSatTrendChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Avg Cost per Employee (EUR)",
          data: costs,
          borderColor: "#E65100",
          backgroundColor: "rgba(230,81,0,0.08)",
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: "#E65100",
          fill: true,
          tension: 0.3,
          yAxisID: "yCost",
        },
        {
          label: "Avg Satisfaction Score",
          data: satisfaction,
          borderColor: "#1565C0",
          backgroundColor: "rgba(21,101,192,0.08)",
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: "#1565C0",
          fill: true,
          tension: 0.3,
          yAxisID: "ySat",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.dataset.label.includes("Cost")
                ? ` ${fmt.eur(ctx.raw)}`
                : ` ${ctx.raw}/10`,
          },
        },
      },
      scales: {
        yCost: {
          type: "linear",
          position: "left",
          grid: GRID_STYLE,
          title: { display: true, text: "Cost (EUR)" },
          ticks: { callback: (v) => fmt.eur(v) },
        },
        ySat: {
          type: "linear",
          position: "right",
          min: 0,
          max: 10,
          grid: { display: false },
          title: { display: true, text: "Satisfaction (1–10)" },
        },
      },
    },
  });
}

// ── NEW: Satisfaction Bands Donut ────────────────────────────────────────────

function buildSatisfactionBandsChart(bands) {
  const order = bands.band_order;
  const data = order.map((b) => bands.overall[b] || 0);
  const BAND_COLOURS = ["#C62828", "#FF8F00", "#1565C0", "#2E7D32"];

  new Chart(document.getElementById("satisfactionBandsChart"), {
    type: "doughnut",
    data: {
      labels: order,
      datasets: [{ data, backgroundColor: BAND_COLOURS, borderWidth: 2, hoverOffset: 8 }],
    },
    options: {
      responsive: true,
      cutout: "55%",
      plugins: {
        legend: { position: "right" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              return ` ${ctx.raw} employees (${((ctx.raw / total) * 100).toFixed(1)}%)`;
            },
          },
        },
      },
    },
  });
}

// ── NEW: Success Factors Bar chart ───────────────────────────────────────────

function buildSuccessFactorsChart(successFactors) {
  // By stream — success rate %
  const streamData = successFactors.by_stream.slice(0, 8);
  const streamLabels = streamData.map((s) => s.stream);

  new Chart(document.getElementById("successStreamChart"), {
    type: "bar",
    data: {
      labels: streamLabels,
      datasets: [
        {
          label: "Successful",
          data: streamData.map((s) => s.successful),
          backgroundColor: "#2E7D32",
          borderRadius: 4,
          stack: "a",
        },
        {
          label: "Unsuccessful",
          data: streamData.map((s) => s.unsuccessful),
          backgroundColor: "#E65100",
          borderRadius: 4,
          stack: "a",
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const s = streamData[items[0].dataIndex];
              return [`  Success rate: ${s.success_rate_pct}%`];
            },
          },
        },
      },
      scales: {
        x: { stacked: true, grid: GRID_STYLE, title: { display: true, text: "Employees" } },
        y: { stacked: true, grid: { display: false } },
      },
    },
  });

  // By experience bucket — success rate
  const expData = successFactors.by_experience;
  const expOrder = ["0-3 yrs","4-7 yrs","8-12 yrs","13-20 yrs","20+ yrs"];
  const expSorted = expOrder
    .map((k) => expData.find((e) => e.experience_bucket === k))
    .filter(Boolean);

  new Chart(document.getElementById("successExpChart"), {
    type: "bar",
    data: {
      labels: expSorted.map((e) => e.experience_bucket),
      datasets: [{
        label: "Success Rate (%)",
        data: expSorted.map((e) => e.success_rate_pct),
        backgroundColor: expSorted.map((_, i) => YEAR_COLOURS[i % YEAR_COLOURS.length]),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.raw}% success rate` } },
      },
      scales: {
        y: { min: 0, max: 100, grid: GRID_STYLE, title: { display: true, text: "Success Rate (%)" } },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── NEW: Drop-off Rate by Module ──────────────────────────────────────────────

function buildDropOffChart(moduleStats) {
  const moduleLabels = {
    skillbuilder: "Cloud Skillbuilder",
    instructor: "Instructor-Led",
    mytms: "MyTMS",
    game_day: "Game Day",
    hackathon: "Hackathon",
    cert: "Certification",
  };
  const entries = Object.entries(moduleStats).map(([k, v]) => ({
    label: moduleLabels[k] || k,
    drop_off: v.drop_off_rate_pct,
    completion: v.completion_rate_pct,
  })).sort((a, b) => b.drop_off - a.drop_off);

  new Chart(document.getElementById("dropOffChart"), {
    type: "bar",
    data: {
      labels: entries.map((e) => e.label),
      datasets: [
        {
          label: "Drop-off Rate (%)",
          data: entries.map((e) => e.drop_off),
          backgroundColor: "#C62828",
          borderRadius: 6,
          yAxisID: "y",
        },
        {
          label: "Completion Rate (%)",
          data: entries.map((e) => e.completion),
          type: "line",
          borderColor: "#2E7D32",
          borderWidth: 2.5,
          pointRadius: 5,
          pointBackgroundColor: "#2E7D32",
          tension: 0.3,
          yAxisID: "y",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top" } },
      scales: {
        y: { min: 0, max: 100, grid: GRID_STYLE, title: { display: true, text: "%" } },
        x: { grid: { display: false } },
      },
    },
  });
}

// ── Entry point ─────────────────────────────────────────────────────────────

async function initDashboard() {
  auth.requireAuth();

  try {
    const response = await fetch(CONFIG.DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    const data = await response.json();

    populateSummaryCards(data);
    buildYearChart(data.by_year);
    buildSatisfactionChart(data.by_year);
    buildModuleChart(data.module_stats);
    buildStreamChart(data.by_stream);
    buildQ8Chart(data.q8_most_valuable);
    buildQ11Chart(data.q11_prefer_platform_academy);
    buildCostPerStreamChart(data.by_stream);
    // New charts
    buildROIScatterChart(data.roi_scores);
    buildROITable(data.roi_scores);
    buildCostSatisfactionTrendChart(data.by_year);
    buildSatisfactionBandsChart(data.satisfaction_bands);
    buildSuccessFactorsChart(data.success_factors);
    buildDropOffChart(data.module_stats);

    hideLoading();
  } catch (err) {
    console.error("Dashboard load error:", err);
    showError(`Could not load dashboard data.<br><code>${err.message}</code>`);
  }
}

document.addEventListener("DOMContentLoaded", initDashboard);
