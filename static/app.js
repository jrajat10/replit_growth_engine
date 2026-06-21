let segment = "consumer";
let state = null;
let memo = null;
let trends = null;

let spendChart = null;
let cacChart = null;
let allocChart = null;

// ── TOAST ─────────────────────────────────────────
function toast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 260);
  }, 3500);
}

// ── LOADING ───────────────────────────────────────
function setLoading(on) {
  document.getElementById("loading-overlay").classList.toggle("active", on);
}

// ── FETCH ─────────────────────────────────────────
async function loadState() {
  setLoading(true);
  try {
    const [stateRes, trendsRes] = await Promise.all([
      fetch(`/api/state?segment=${segment}`),
      fetch(`/api/trends?segment=${segment}`),
    ]);
    const stateData = await stateRes.json();
    const trendsData = await trendsRes.json();
    state = stateData.state;
    memo = stateData.memo;
    trends = trendsData;
    renderAll();
  } catch {
    toast("Failed to load data. Check server connection.", "error");
  } finally {
    setLoading(false);
  }
}

function renderAll() {
  if (!state) return;
  document.getElementById("week-label").textContent = state.week_label;
  const mi = document.getElementById("model-indicator");
  if (state.model?.available) {
    mi.textContent = `MODEL · ${state.model.version}`;
    mi.classList.remove("hidden");
  } else {
    mi.classList.add("hidden");
  }
  renderBrief();
  renderAllocation();
  renderPerformance();
  renderFunnel();
  renderCompetition();
  renderRoadmap();
  renderExperiments();
  renderCreatives();
  renderData();
}

// ── DELTA HELPERS ─────────────────────────────────
function deltaClass(wowStr, invertGood = false) {
  const isPos = wowStr?.startsWith("+");
  const isNeg = wowStr?.startsWith("−") || wowStr?.startsWith("-");
  if (!isPos && !isNeg) return "delta-neutral";
  const good = invertGood ? isNeg : isPos;
  return good ? "delta-up" : "delta-down";
}

function deltaArrow(wowStr, invertGood = false) {
  const isPos = wowStr?.startsWith("+");
  const isNeg = wowStr?.startsWith("−") || wowStr?.startsWith("-");
  if (!isPos && !isNeg) return "";
  const good = invertGood ? isNeg : isPos;
  return good ? "▲ " : "▼ ";
}

// ── CAC COLOR ─────────────────────────────────────
function cacClass(cac, target) {
  if (!target || !cac) return "";
  const v = parseFloat(cac);
  if (v >= target) return "cac-over";
  if (v >= target * 0.85) return "cac-warn";
  return "cac-good";
}

// ── BRIEF ─────────────────────────────────────────
function renderBrief() {
  document.getElementById("brief-title").textContent = memo.title;
  document.getElementById("segment-context").textContent = memo.segment_context;

  // Priority actions
  const actions = memo.priority_actions || [];
  document.getElementById("priority-actions").innerHTML = actions.length
    ? actions.map((a, i) => `
      <div class="action-card priority-${a.priority}">
        <div class="action-header">
          <span class="action-rank">0${i + 1}</span>
          <span class="action-priority-badge ${a.priority}">${a.priority.toUpperCase()}</span>
          <span class="action-owner">${a.owner}</span>
        </div>
        <div class="action-text">${a.action}</div>
        <div class="action-reason">${a.reason}</div>
      </div>`).join("")
    : "";

  // Intel strip — 4 tiles
  const kpis = state.kpis;
  const cacPct = Math.min(100, Math.round((kpis.cac.value / kpis.cac.target) * 100));
  const cacMeterClass = kpis.cac.value >= kpis.cac.target ? "meter-over"
    : kpis.cac.value >= kpis.cac.target * 0.85 ? "meter-warn" : "meter-ok";

  const qcacVal = kpis.qcac?.value;
  const ratio = kpis.qcac?.ratio_to_cac;
  const tiles = [
    { label: "Weekly Spend", value: `$${(kpis.spend.value / 1000).toFixed(0)}k`,             delta: kpis.spend.fmt_wow,           inv: false, target: null },
    { label: "CAC",          value: `$${Math.round(kpis.cac.value)}`,                        delta: kpis.cac.fmt_wow,             inv: true,  target: `Ceiling $${kpis.cac.target}`, meter: cacPct, meterClass: cacMeterClass },
    { label: "qCAC",         value: qcacVal ? `$${Math.round(qcacVal).toLocaleString()}` : "—", delta: ratio ? `${ratio}× CAC` : "", inv: false, target: "spend / paying user" },
    { label: "Net-new Conv", value: Math.round(kpis.new_conversions.value).toLocaleString(),  delta: kpis.new_conversions.fmt_wow, inv: false, target: null },
  ];

  document.getElementById("intel-strip").innerHTML = tiles.map(t => `
    <div class="intel-tile">
      <div class="tile-label">${t.label}</div>
      <div class="tile-value">${t.value}</div>
      <div class="tile-delta ${deltaClass(t.delta, t.inv)}">${deltaArrow(t.delta, t.inv)}${t.delta || "—"} WoW</div>
      ${t.target ? `<div class="tile-target">${t.target}</div>` : ""}
      ${t.meter != null ? `<div class="tile-meter"><div class="tile-meter-fill ${t.meterClass}" style="width:${t.meter}%"></div></div>` : ""}
    </div>`).join("");

  // Signal bullets
  document.getElementById("brief-bullets").innerHTML = memo.headline_bullets
    .map(b => `<div class="bullet-item">${b}</div>`).join("");

  // Counterfactual
  document.getElementById("counterfactual").innerHTML =
    `<strong>Counterfactual:</strong> ${memo.counterfactual}`;

  // Decisions pending
  const decisions = memo.decisions_pending;
  document.getElementById("decisions-count").textContent = decisions.length;
  document.getElementById("decisions-list").innerHTML = decisions.length
    ? decisions.map(d => `
      <div class="decision-card">
        <div class="decision-card-header">
          <h4>${d.title}</h4>
          <span class="status-pending">PENDING</span>
        </div>
        <p>${d.summary}</p>
        ${d.details?.length ? `<ul>${d.details.map(x => `<li>${x}</li>`).join("")}</ul>` : ""}
      </div>`).join("")
    : `<p style="font-size:12px;color:var(--muted)">No decisions pending.</p>`;

  // Nav badge
  const briefBadge = document.getElementById("nav-badge-brief");
  briefBadge.textContent = decisions.length;
  briefBadge.classList.toggle("hidden", decisions.length === 0);

  // Decision ledger
  const ledger = state.ledger || [];
  document.getElementById("ledger-list").innerHTML = ledger.length
    ? ledger.map(r => `<div class="ledger-item">
        <span class="ledger-time">${r.timestamp?.slice(0, 16) || "—"}</span>
        <span class="ledger-type">${r.type || ""}</span>
        <span class="ledger-content">${r.summary || r.message || r.learning || ""}</span>
        ${r.human_action ? `<span class="ledger-action">${r.human_action}</span>` : "<span></span>"}
      </div>`).join("")
    : `<p style="font-size:12px;color:var(--muted)">No decisions logged yet.</p>`;

  // Contextual question chips
  renderQuestionChips();
}

// ── QUESTION CHIPS ────────────────────────────────
function renderQuestionChips() {
  const chips = ["Top priority this week"];

  if (state.alerts?.length > 0) {
    chips.push("What's wrong this week?");
  } else {
    chips.push("What's performing best?");
  }

  const latam = state.geo?.find(g => g.geo === "LATAM" && g.flag);
  if (latam) {
    chips.push("Explain LATAM geo drag");
  } else {
    chips.push("Which channel to cut?");
  }

  const cac = state.kpis?.cac;
  if (cac && cac.value > cac.target * 0.85) {
    chips.push("Why is CAC high?");
  } else {
    chips.push("Explain the allocation");
  }

  document.getElementById("question-chips").innerHTML = chips
    .map(q => `<button class="question-chip" data-question="${q}">${q}</button>`)
    .join("");

  document.querySelectorAll(".question-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.getElementById("ask-input").value = chip.dataset.question;
      document.getElementById("ask-btn").click();
    });
  });
}

// ── ALLOCATION ────────────────────────────────────
function renderAllocation() {
  const a = state.allocation;
  document.getElementById("alloc-summary").innerHTML =
    `<h3>Recommendation</h3><p>${a.summary}</p><p class="method">${a.method}</p>`;

  const maxDelta = Math.max(...a.rationale.map(r => Math.abs(r.delta)), 1);
  const cacTarget = state.kpis.cac.target;

  document.querySelector("#alloc-table tbody").innerHTML = a.rationale.map(r => {
    const barW = Math.round((Math.abs(r.delta) / maxDelta) * 100);
    const barDir = r.delta >= 0 ? "pos" : "neg";
    const cacCls = cacClass(r.cac, cacTarget);
    return `<tr>
      <td><strong>${r.label}</strong></td>
      <td>$${r.current_spend.toLocaleString()}</td>
      <td>$${r.recommended_spend.toLocaleString()}</td>
      <td>
        <div class="delta-cell">
          <span class="${r.delta >= 0 ? "delta-pos" : "delta-neg"}">${r.delta >= 0 ? "+" : ""}$${Math.abs(r.delta).toLocaleString()}</span>
          <div class="delta-bar-wrap"><div class="delta-bar delta-bar-${barDir}" style="width:${barW}%"></div></div>
        </div>
      </td>
      <td class="${cacCls}">$${r.cac}</td>
      <td style="font-size:12px;color:var(--text-2)">${r.score_plain}</td>
    </tr>`;
  }).join("");

  renderAllocChart(a.rationale);
}

function renderAllocChart(rationale) {
  const ctx = document.getElementById("allocChart")?.getContext("2d");
  if (!ctx) return;
  if (allocChart) { allocChart.destroy(); allocChart = null; }

  allocChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rationale.map(r => r.label),
      datasets: [
        {
          label: "Current",
          data: rationale.map(r => r.current_spend),
          backgroundColor: "rgba(72,72,100,0.45)",
          borderColor: "rgba(72,72,100,0.7)",
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          label: "Recommended",
          data: rationale.map(r => r.recommended_spend),
          backgroundColor: "rgba(242,98,7,0.55)",
          borderColor: "rgba(242,98,7,0.85)",
          borderWidth: 1,
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      plugins: {
        legend: { labels: { color: "#8484a8", font: { size: 11, family: "Inter, system-ui" }, boxWidth: 12 } },
        tooltip: {
          backgroundColor: "#19192a",
          borderColor: "#2a2a3e",
          borderWidth: 1,
          titleColor: "#ededf7",
          bodyColor: "#8484a8",
          callbacks: { label: c => ` ${c.dataset.label}: $${c.raw.toLocaleString()}` },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(30,30,44,0.8)" },
          ticks: { color: "#4a4a6e", font: { size: 10, family: "Inter, system-ui" }, callback: v => `$${(v / 1000).toFixed(0)}k` },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#8484a8", font: { size: 11, family: "Inter, system-ui" } },
        },
      },
    },
  });
}

// ── PERFORMANCE ───────────────────────────────────
function renderPerformance() {
  const kpis = state.kpis;
  const cacTarget = kpis.cac.target;

  const qcacVal = kpis.qcac?.value;
  const ratio = kpis.qcac?.ratio_to_cac;
  const defs = [
    { label: "Spend",        value: `$${kpis.spend.value.toLocaleString()}`,              wow: kpis.spend.fmt_wow,          inv: false },
    { label: "Net-new Conv", value: Math.round(kpis.new_conversions.value).toLocaleString(), wow: kpis.new_conversions.fmt_wow, inv: false },
    { label: "CAC",          value: `$${Math.round(kpis.cac.value)}`,                    wow: kpis.cac.fmt_wow,            inv: true,  target: `Ceiling $${cacTarget}` },
    { label: "qCAC",         value: qcacVal ? `$${Math.round(qcacVal).toLocaleString()}` : "—", wow: ratio ? `${ratio}× CAC` : "", inv: false, target: "spend / paying user" },
    { label: "Payback",      value: `${kpis.payback_months.value.toFixed(1)} mo`,         wow: kpis.payback_months.fmt_wow, inv: true,  target: `Target ${kpis.payback_months.target} mo` },
    { label: "Net-new %",    value: `${(kpis.net_new_pct.value * 100).toFixed(0)}%`,      wow: kpis.net_new_pct.fmt_wow,    inv: false },
  ];

  document.getElementById("kpi-row").innerHTML = defs.map(k => `
    <div class="kpi">
      <div class="label">${k.label}</div>
      <div class="value">${k.value}</div>
      <div class="delta ${deltaClass(k.wow, k.inv)}">${deltaArrow(k.wow, k.inv)}${k.wow || "—"} WoW</div>
      ${k.target ? `<div class="target-line">${k.target}</div>` : ""}
    </div>`).join("");

  document.getElementById("alerts-box").innerHTML = (state.alerts || [])
    .map(a => {
      const ctx = a.competitor_context;
      const ctxHtml = ctx ? `
        <div class="alert-comp-context">
          <strong>Market read:</strong> ${ctx.explanation}
          <div style="margin-top:4px;font-size:11.5px;color:var(--text-2)">
            Confidence ${(ctx.confidence * 100).toFixed(0)}% &middot; Source: ${ctx.source}
          </div>
          <div style="margin-top:4px;font-size:12px"><em>${ctx.framing}</em></div>
        </div>` : "";
      return `<div class="alert alert-${a.severity}">
        <div><strong>${a.title}</strong> — ${a.message}</div>
        ${ctxHtml}
      </div>`;
    }).join("");

  // Channel table — color-code CAC vs ceiling
  document.querySelector("#channel-table tbody").innerHTML = state.channels
    .map(c => {
      const pct = c.cac_wow?.pct;
      const wowStr = pct != null ? `${pct >= 0 ? "+" : ""}${(pct * 100).toFixed(1)}%` : "—";
      const wowCls = pct != null ? (pct > 0 ? "delta-neg" : "delta-pos") : "";
      const cCls = cacClass(c.cac, cacTarget);
      return `<tr>
        <td><strong>${c.label}</strong></td>
        <td>$${c.spend.toLocaleString()}</td>
        <td>${c.new_conversions.toLocaleString()}</td>
        <td class="${cCls}">$${c.cac}</td>
        <td class="${wowCls}">${wowStr}</td>
      </tr>`;
    }).join("");

  // Geo table — color-code CAC
  document.querySelector("#geo-table tbody").innerHTML = state.geo
    .map(g => {
      const geoCacTarget = cacTarget * g.arpu_multiplier;
      const cCls = cacClass(g.cac, geoCacTarget);
      return `<tr>
        <td>${g.geo}</td>
        <td>$${g.spend.toLocaleString()}</td>
        <td>${g.new_conversions}</td>
        <td class="${cCls}">$${g.cac}</td>
        <td>${g.arpu_multiplier}×</td>
        <td class="flag">${g.flag || ""}</td>
      </tr>`;
    }).join("");

  // Paid campaigns (Instagram UTMs)
  renderPaidCampaigns();

  // Attribution
  const attr = state.attribution;
  document.getElementById("attribution-box").innerHTML = `
    <div class="panel-block-label">ATTRIBUTION DIAGNOSTIC</div>
    <p style="margin-bottom:6px"><strong>${attr.headline || "Attribution"}</strong></p>
    <p style="font-size:13px;color:var(--text-2);margin-bottom:8px;line-height:1.6">${attr.simple_explanation || ""}</p>
    <p style="font-size:13px"><strong>Key diagnostic:</strong> ${attr.retargeting_diagnostic?.plain_english || ""}</p>
    <p style="font-size:12px;color:var(--text-2);margin-top:6px;line-height:1.55">${attr.action || ""}</p>`;

  if (trends?.weeks?.length) renderTrendCharts(trends.weeks);
}

function renderPaidCampaigns() {
  const box = document.getElementById("paid-campaigns-box");
  if (!box) return;
  const pc = state.paid_campaigns;
  if (!pc?.campaigns?.length) {
    box.innerHTML = "";
    return;
  }
  const lp = pc.landing_page || {};
  box.innerHTML = `
    <div class="panel-block-label">LIVE INSTAGRAM CAMPAIGNS (UTM CAPTURE)</div>
    <p class="panel-note">Decoded from live ad links · ${pc.source_medium || "ig / paid"} · LP: ${lp.hero || "replit.com"}</p>
    ${pc.insights?.map(i => `<div class="alert alert-medium" style="margin-bottom:8px">${i}</div>`).join("") || ""}
    ${pc.campaigns.map(c => `
      <div class="decision-card" style="margin-top:12px">
        <h4>${c.name} <span class="status">${c.status}</span></h4>
        <p><strong>utm_content:</strong> <code>${c.utm_content}</code></p>
        <p><strong>Message match:</strong> ${(c.message_match_score * 100).toFixed(0)}% — ${c.message_match_note}</p>
        <p><strong>Taxonomy:</strong> ${c.taxonomy?.format || "—"} / ${c.taxonomy?.theme || c.taxonomy?.meta_creative_id || "—"} / ${c.taxonomy?.type || "—"}</p>
        ${c.estimated_weekly_spend ? `<p><strong>Est. spend (Meta prospecting share):</strong> $${c.estimated_weekly_spend.toLocaleString()}</p>` : ""}
        <ul>${(c.learnings || []).map(l => `<li>${l}</li>`).join("")}</ul>
      </div>`).join("")}
  `;
}

function renderTrendCharts(weeks) {
  const labels = weeks.map(w => w.label);
  const cacTarget = state?.kpis?.cac?.target;

  const sharedOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: "#8484a8", font: { size: 10, family: "Inter, system-ui" }, boxWidth: 10 },
      },
      tooltip: {
        backgroundColor: "#19192a",
        borderColor: "#2a2a3e",
        borderWidth: 1,
        titleColor: "#ededf7",
        bodyColor: "#8484a8",
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(30,30,44,0.7)" },
        ticks: { color: "#4a4a6e", font: { size: 10, family: "Inter, system-ui" }, maxTicksLimit: 6 },
      },
      y: {
        grid: { color: "rgba(30,30,44,0.7)" },
        ticks: { color: "#4a4a6e", font: { size: 10, family: "Inter, system-ui" } },
      },
    },
  };

  // Spend trend
  const spendCtx = document.getElementById("spendTrendChart")?.getContext("2d");
  if (spendCtx) {
    if (spendChart) { spendChart.destroy(); spendChart = null; }
    spendChart = new Chart(spendCtx, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Spend",
          data: weeks.map(w => w.spend),
          borderColor: "rgba(242,98,7,0.9)",
          backgroundColor: "rgba(242,98,7,0.06)",
          fill: true, tension: 0.35,
          pointRadius: 3, pointBackgroundColor: "#f26207",
          pointHoverRadius: 5,
        }],
      },
      options: {
        ...sharedOptions,
        scales: {
          ...sharedOptions.scales,
          y: {
            ...sharedOptions.scales.y,
            ticks: { ...sharedOptions.scales.y.ticks, callback: v => `$${(v / 1000).toFixed(0)}k` },
          },
        },
      },
    });
  }

  // CAC trend — with target reference line
  const cacCtx = document.getElementById("cacTrendChart")?.getContext("2d");
  if (cacCtx) {
    if (cacChart) { cacChart.destroy(); cacChart = null; }
    const datasets = [{
      label: "CAC",
      data: weeks.map(w => w.cac),
      borderColor: "rgba(16,185,129,0.9)",
      backgroundColor: "rgba(16,185,129,0.05)",
      fill: true, tension: 0.35,
      pointRadius: 3, pointBackgroundColor: "#10b981",
      pointHoverRadius: 5,
    }];
    if (cacTarget) {
      datasets.push({
        label: `Ceiling $${cacTarget}`,
        data: Array(labels.length).fill(cacTarget),
        borderColor: "rgba(245,158,11,0.50)",
        borderDash: [5, 4],
        pointRadius: 0,
        fill: false,
        tension: 0,
      });
    }
    cacChart = new Chart(cacCtx, {
      type: "line",
      data: { labels, datasets },
      options: {
        ...sharedOptions,
        scales: {
          ...sharedOptions.scales,
          y: {
            ...sharedOptions.scales.y,
            ticks: { ...sharedOptions.scales.y.ticks, callback: v => `$${v}` },
          },
        },
      },
    });
  }
}

// ── FUNNEL ────────────────────────────────────────
function renderFunnel() {
  const f = state.funnel;
  if (!f) return;

  const rateClass = (pct) => pct >= 40 ? "" : pct >= 25 ? "weak" : "bad";

  const tiles = [
    { label: "CAC",            value: `$${Math.round(f.cac).toLocaleString()}`, sub: "spend / signup" },
    { label: "qCAC",           value: `$${Math.round(f.qcac).toLocaleString()}`, sub: `${f.qcac_to_cac_ratio}× CAC — spend / paid` },
    { label: "Activation Rate",value: `${f.activation_rate}%`,                  sub: "signup → published in 7d" },
    { label: "Free→Paid",      value: `${f.free_to_paid_rate}%`,                sub: "of activated users" },
    { label: "Prompt-Start",   value: `${f.prompt_start_rate}%`,                sub: "of landing visits" },
  ];
  document.getElementById("funnel-kpi-row").innerHTML = tiles.map(t => `
    <div class="kpi">
      <div class="label">${t.label}</div>
      <div class="value">${t.value}</div>
      <div class="target-line">${t.sub}</div>
    </div>`).join("");

  document.getElementById("funnel-stages").innerHTML = (f.stages || []).map(s => {
    const ratePct = s.rate_from_prior != null ? (s.rate_from_prior * 100) : null;
    const rateText = ratePct != null ? `${ratePct.toFixed(1)}% from prior` : "&nbsp;";
    const cls = ratePct != null ? rateClass(ratePct) : "";
    return `<div class="funnel-stage">
      <div class="funnel-stage-label">${s.stage}</div>
      <div class="funnel-stage-value">${s.value.toLocaleString()}</div>
      <div class="funnel-stage-rate ${cls}">${rateText}</div>
    </div>`;
  }).join("");

  document.getElementById("funnel-definitions").innerHTML =
    `<strong>Activation:</strong> ${f.definitions?.activation || ""}<br><strong>qCAC:</strong> ${f.definitions?.qcac || ""}`;

  // Channel table
  const channels = state.funnel_channels || [];
  document.querySelector("#funnel-channel-table tbody").innerHTML = channels.map(c => `
    <tr>
      <td><strong>${c.label}</strong></td>
      <td>$${c.spend.toLocaleString()}</td>
      <td>${c.signups.toLocaleString()}</td>
      <td>${c.activated.toLocaleString()}</td>
      <td>${c.paid}</td>
      <td>$${c.cac.toLocaleString()}</td>
      <td>$${c.qcac.toLocaleString()}</td>
      <td>${c.activation_rate_pct}%</td>
      <td>${c.free_to_paid_pct}%</td>
      <td>${c.quality_flag ? `<span class="flag-pill flag-${c.quality_flag}">${c.quality_flag.replace(/_/g, " ")}</span>` : ""}</td>
    </tr>`).join("");

  // Forecast
  const fc = state.funnel_forecast;
  const fcBox = document.getElementById("funnel-forecast-box");
  if (fc?.available) {
    const rows = fc.rows.map(r => `
      <tr>
        <td><strong>${r.label}</strong></td>
        <td>${r.activated_this_week.toLocaleString()}</td>
        <td>${r.cohort_paid_rate_pct}%</td>
        <td><strong>${r.forecast_paid}</strong></td>
      </tr>`).join("");
    fcBox.innerHTML = `
      <div class="panel-block-label">FREE→PAID FORECAST (BLENDED SIGNAL)</div>
      <p class="panel-note">${fc.method}. Cohort weeks: ${fc.cohort_weeks.length} (lag ${fc.lag_weeks}w).</p>
      <table class="data-table">
        <thead><tr><th>Channel</th><th>Activated (this week)</th><th>Cohort Paid Rate</th><th>Forecast Paid</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr><td colspan="3" style="text-align:right;font-weight:600">Total forecast paid:</td><td><strong>${fc.total_forecast_paid}</strong></td></tr></tfoot>
      </table>
      <p class="panel-note" style="margin-top:8px"><em>${fc.note}</em></p>`;
  } else {
    fcBox.innerHTML = "";
  }

  // Time to first app gap
  const ttf = state.time_to_first_app;
  document.getElementById("time-to-first-app-box").innerHTML = ttf?.available === false
    ? `<div class="panel-block-label">TIME-TO-FIRST-APP</div>
       <p class="panel-note"><em>${ttf.note}</em></p>`
    : "";
}

// ── COMPETITION ───────────────────────────────────
function renderCompetition() {
  const comp = state.competition;
  if (!comp) return;

  document.getElementById("competition-discipline").innerHTML = `
    <div class="panel-block-label">DISCIPLINE</div>
    <p class="panel-note"><em>${comp.discipline_note}</em></p>
    <p style="font-size:12px;color:var(--text-2);margin-top:6px">
      <strong>Sources in use:</strong> ${(comp.sources_in_use || []).join(" · ") || "—"}
    </p>`;

  document.getElementById("competition-landscape").innerHTML = `
    <div class="panel-block-label">LANDSCAPE</div>
    ${(comp.competitors || []).map(c => `
      <div class="comp-card">
        <h4>${c.name} <span class="status">${c.primary_threat_segment}</span></h4>
        <p>${c.positioning}</p>
        <div class="comp-meta">
          <span>${c.headline_metric}</span>
          <span>${c.funding}</span>
          <span>${c.users}</span>
        </div>
      </div>`).join("")}`;

  document.getElementById("competition-signals").innerHTML = `
    <div class="panel-block-label">RECENT SIGNALS (HAND-AUTHORED, v0)</div>
    ${(comp.recent_signals || []).map(s => `
      <div class="comp-card">
        <h4>${s.competitor_id} — ${s.signal_type} <span class="status">${s.value}</span></h4>
        <p><strong>Interpretation:</strong> ${s.interpretation}</p>
        <p><strong>Implication:</strong> ${s.implication}</p>
        <div class="comp-meta">
          <span>Confidence ${(s.confidence * 100).toFixed(0)}%
            <span class="confidence-bar"><span class="confidence-fill" style="width:${s.confidence * 100}%"></span></span>
          </span>
          <span>Source: ${s.source}</span>
          <span>${s.channel}</span>
        </div>
      </div>`).join("") || "<p class='panel-note'>No signals captured this week.</p>"}`;

  // Alerts that the competitor lens explained
  const explained = (state.alerts || []).filter(a => a.competitor_context);
  const compBadge = document.getElementById("nav-badge-comp");
  if (compBadge) {
    compBadge.textContent = explained.length;
    compBadge.classList.toggle("hidden", explained.length === 0);
  }
  document.getElementById("competition-explained-alerts").innerHTML = explained.length
    ? `<div class="panel-block-label">EXPLAINED ALERTS THIS WEEK</div>
       ${explained.map(a => `
        <div class="comp-card">
          <h4>${a.title}</h4>
          <p>${a.message}</p>
          <p style="margin-top:6px"><strong>Market read:</strong> ${a.competitor_context.explanation}</p>
          <p><em>${a.competitor_context.framing}</em></p>
        </div>`).join("")}`
    : `<div class="panel-block-label">EXPLAINED ALERTS THIS WEEK</div>
       <p class='panel-note'>No alerts this week traced to competitor activity.</p>`;
}

// ── ROADMAP ───────────────────────────────────────
function renderRoadmap() {
  const r = state.roadmap;
  if (!r) return;
  document.getElementById("roadmap-title").textContent = r.title;
  document.getElementById("roadmap-tagline").textContent = r.tagline;
  document.getElementById("roadmap-grid").innerHTML = r.versions.map(v => `
    <article class="roadmap-card status-${v.status}">
      <header>
        <span class="s-version-pill">${v.version}</span>
        <span class="s-status-pill ${v.status === "shipped" ? "" : v.status === "next" ? "next" : "planned"}">${v.status.toUpperCase()}</span>
      </header>
      <h3>${v.title}</h3>
      <ul>${v.items.map(i => `<li>${i}</li>`).join("")}</ul>
    </article>`).join("");
}

// ── EXPERIMENTS ───────────────────────────────────
function renderExperiments() {
  const exps = state.experiments || [];

  const expBadge = document.getElementById("nav-badge-experiments");
  const actionable = exps.filter(e => ["ship", "stop"].includes(e.recommendation) && e.status === "running");
  expBadge.textContent = actionable.length;
  expBadge.classList.toggle("hidden", actionable.length === 0);

  document.getElementById("experiments-list").innerHTML = exps.length
    ? exps.map(e => `
      <div class="exp-card">
        <div class="exp-header">
          <span class="exp-badge ${e.type === "geo_holdout" ? "badge-holdout" : "badge-ab"}">${e.type === "geo_holdout" ? "GEO HOLDOUT" : "A/B TEST"}</span>
          <h3>${e.name}</h3>
        </div>
        <p class="exp-hypothesis">${e.hypothesis}</p>
        <p style="font-size:13px;margin-bottom:12px;color:var(--text-2)">${e.plain_english}</p>
        <div class="exp-stats">
          <div class="exp-stat"><span class="exp-stat-label">Control</span><span class="exp-stat-value">${e.control_rate}%</span></div>
          <div class="exp-stat"><span class="exp-stat-label">Variant</span><span class="exp-stat-value">${e.variant_rate}%</span></div>
          <div class="exp-stat"><span class="exp-stat-label">Lift</span><span class="exp-stat-value">${e.lift_pct}%</span></div>
          <div class="exp-stat"><span class="exp-stat-label">p-value</span><span class="exp-stat-value">${e.p_value}</span></div>
        </div>
        <div class="exp-rec rec-${e.recommendation}">→ ${e.recommendation_text}</div>
        ${e.learning ? `<p class="exp-learning" style="margin-top:6px"><strong>Learning:</strong> ${e.learning}</p>` : ""}
      </div>`).join("")
    : `<p style="font-size:13px;color:var(--muted)">No experiments for this segment.</p>`;
}

// ── CREATIVES ─────────────────────────────────────
function renderCreatives() {
  document.getElementById("insight-cards").innerHTML =
    (state.creative_cards || []).map(c => `
      <div class="insight-card fatigue-${c.fatigue}">
        <div class="insight-header">
          <h3>${c.name}</h3>
          <span class="fatigue-pill">${c.fatigue} fatigue</span>
        </div>
        <p class="insight-row"><strong>Channel:</strong> ${c.channel_label} &nbsp;·&nbsp; <strong>Directive:</strong> ${c.directive_text}</p>
        <p class="insight-row"><strong>Finding:</strong> ${c.finding}</p>
        <p class="insight-row"><strong>Hypothesis:</strong> ${c.hypothesis}</p>
        <p class="insight-row"><strong>Recommendation:</strong> ${c.recommend_to_brand}</p>
        <div class="insight-handoff">→ Insight card forwarded to Brand team · Growth tests; Brand owns copy</div>
      </div>`).join("");
}

// ── SYSTEM ────────────────────────────────────────
function renderData() {
  const ds = state.data_source;
  const m = state.model || {};

  document.getElementById("data-status").innerHTML = `
    <div class="panel-block-label">WAREHOUSE CONNECTION</div>
    <p style="font-size:13px;margin-bottom:5px"><strong>Source:</strong> ${ds.label}</p>
    <p style="font-size:13px;margin-bottom:5px"><strong>Path:</strong> ${ds.path}</p>
    <p style="font-size:13px"><strong>Status:</strong> ${ds.connected ? "Connected" : "Disconnected"}</p>`;

  document.getElementById("model-status").innerHTML = m.available
    ? `<div class="panel-block-label">DS MODEL</div>
       <p style="font-size:13px;margin-bottom:5px"><strong>Version:</strong> ${m.version}</p>
       <p style="font-size:13px;margin-bottom:5px"><strong>Source:</strong> ${m.source}</p>
       <p style="font-size:13px;margin-bottom:8px"><strong>Scored:</strong> ${m.scored_at || "—"}</p>
       <p style="font-size:12px;color:var(--text-2);line-height:1.55">Allocator uses DS efficiency_score when confidence ≥ 50%; heuristic fallback otherwise.</p>`
    : `<div class="panel-block-label">DS MODEL</div>
       <p style="font-size:13px;margin-bottom:6px">Model not available — allocator running heuristic (net-new/$ × LTV).</p>
       <p style="font-size:12px;color:var(--muted)">DS team publishes to ml_channel_scores weekly.</p>`;
}

// ── TABS ──────────────────────────────────────────
document.getElementById("tabs").addEventListener("click", e => {
  const btn = e.target.closest(".nav-item");
  if (!btn?.dataset.tab) return;
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  if (btn.dataset.tab === "performance" && trends?.weeks?.length) setTimeout(() => renderTrendCharts(trends.weeks), 50);
  if (btn.dataset.tab === "allocation" && state?.allocation) setTimeout(() => renderAllocChart(state.allocation.rationale), 50);
});

// ── SEGMENT ───────────────────────────────────────
document.getElementById("segment-toggle").addEventListener("click", e => {
  if (e.target.tagName !== "BUTTON") return;
  segment = e.target.dataset.segment;
  document.querySelectorAll(".segment-toggle button").forEach(b => b.classList.remove("active"));
  e.target.classList.add("active");
  loadState();
});

// ── ASK ───────────────────────────────────────────
document.getElementById("ask-btn").addEventListener("click", async () => {
  const q = document.getElementById("ask-input").value.trim();
  if (!q) return;
  const btn = document.getElementById("ask-btn");
  btn.disabled = true;
  btn.textContent = "…";
  const result = document.getElementById("ask-result");
  result.classList.add("hidden");
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, segment }),
    });
    const data = await res.json();
    result.classList.remove("hidden");
    result.innerHTML = `<p style="line-height:1.65">${data.answer}</p>
      <p class="sources">Sources: ${(data.sources || []).join(", ")}</p>`;
  } catch {
    toast("Query failed. Try again.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask";
  }
});

document.getElementById("ask-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("ask-btn").click();
});

document.getElementById("ask-input").addEventListener("input", () => {
  document.getElementById("ask-result").classList.add("hidden");
});

// ── APPROVE ───────────────────────────────────────
document.getElementById("approve-alloc").addEventListener("click", async () => {
  const btn = document.getElementById("approve-alloc");
  btn.disabled = true;
  try {
    const res = await fetch("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segment, decision_id: "alloc_main", action: "approved" }),
    });
    const data = await res.json();
    if (data.ok) {
      toast("Allocation approved and logged to decision ledger.", "success");
      loadState();
    }
  } catch {
    toast("Approval failed. Try again.", "error");
  } finally {
    btn.disabled = false;
  }
});

// ── RESYNC ────────────────────────────────────────
document.getElementById("resync-btn")?.addEventListener("click", async () => {
  setLoading(true);
  try {
    await fetch("/api/sync", { method: "POST" });
    await loadState();
    toast("Data re-synced from source.", "success");
  } catch {
    toast("Sync failed.", "error");
  } finally {
    setLoading(false);
  }
});

// ── INIT ──────────────────────────────────────────
loadState();

// ── CHAT WIDGET ───────────────────────────────────
let chatHistory = [];

function openChat() {
  document.getElementById("chat-panel").classList.add("open");
  document.getElementById("chat-input").focus();
}

function closeChat() {
  document.getElementById("chat-panel").classList.remove("open");
}

function resetChatWelcome() {
  document.getElementById("chat-messages").innerHTML = `
    <div class="chat-welcome">
      <p>Ask me anything about this week's growth programs — channels, CAC, budget allocation, experiments, geo performance, or creative fatigue.</p>
      <div class="chat-suggestions">
        <button class="chat-suggestion">What's the top priority this week?</button>
        <button class="chat-suggestion">Give me an overview</button>
        <button class="chat-suggestion">Which channel to cut?</button>
        <button class="chat-suggestion">Explain the LATAM drag</button>
        <button class="chat-suggestion">What experiments should we ship?</button>
        <button class="chat-suggestion">What's the full channel mix?</button>
      </div>
    </div>`;
  document.querySelectorAll(".chat-suggestion").forEach(btn => {
    btn.addEventListener("click", () => {
      document.getElementById("chat-input").value = btn.textContent;
      sendChatMessage();
    });
  });
}

document.getElementById("chat-toggle-btn").addEventListener("click", () => {
  const panel = document.getElementById("chat-panel");
  panel.classList.contains("open") ? closeChat() : openChat();
});

document.getElementById("chat-close-btn").addEventListener("click", closeChat);

document.getElementById("clear-chat-btn").addEventListener("click", () => {
  chatHistory = [];
  resetChatWelcome();
});

// Cmd+K / Ctrl+K to open chat from anywhere
document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    const panel = document.getElementById("chat-panel");
    panel.classList.contains("open") ? closeChat() : openChat();
  }
});

document.querySelectorAll(".chat-suggestion").forEach(btn => {
  btn.addEventListener("click", () => {
    document.getElementById("chat-input").value = btn.textContent;
    sendChatMessage();
  });
});

document.getElementById("chat-input").addEventListener("keydown", e => {
  if (e.key === "Enter") sendChatMessage();
});

document.getElementById("chat-send-btn").addEventListener("click", sendChatMessage);

function _ts() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function appendChatMessage(role, text, sources) {
  const welcome = document.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const container = document.getElementById("chat-messages");
  const msg = document.createElement("div");
  msg.className = `chat-msg chat-msg-${role}`;

  if (role === "assistant") {
    const srcHtml = sources?.length ? `<div class="chat-msg-sources">${sources.join(", ")}</div>` : "";
    msg.innerHTML = `
      <div class="chat-msg-label">Assistant <span class="chat-msg-time">${_ts()}</span></div>
      <div class="chat-msg-text">${text}</div>${srcHtml}`;
  } else {
    msg.innerHTML = `
      <div class="chat-msg-time chat-msg-time-user">${_ts()}</div>
      <div class="chat-msg-text">${text}</div>`;
  }

  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

function setChatThinking(on) {
  const existing = document.getElementById("chat-thinking");
  if (on && !existing) {
    const el = document.createElement("div");
    el.id = "chat-thinking";
    el.className = "chat-msg chat-msg-assistant";
    el.innerHTML = `<div class="chat-msg-label">Assistant</div><div class="chat-thinking-dots"><span></span><span></span><span></span></div>`;
    const c = document.getElementById("chat-messages");
    c.appendChild(el);
    c.scrollTop = c.scrollHeight;
  } else if (!on && existing) {
    existing.remove();
  }
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const q = input.value.trim();
  if (!q) return;
  input.value = "";

  openChat();
  appendChatMessage("user", q);
  chatHistory.push({ role: "user", content: q });

  const sendBtn = document.getElementById("chat-send-btn");
  sendBtn.disabled = true;
  setChatThinking(true);

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, segment }),
    });
    const data = await res.json();
    setChatThinking(false);
    appendChatMessage("assistant", data.answer, data.sources);
    chatHistory.push({ role: "assistant", content: data.answer });
  } catch {
    setChatThinking(false);
    appendChatMessage("assistant", "Sorry, I couldn't reach the server. Please try again.");
  } finally {
    sendBtn.disabled = false;
  }
}
