let segment = "consumer";
let state = null;
let memo = null;

async function loadState() {
  const res = await fetch(`/api/state?segment=${segment}`);
  const data = await res.json();
  state = data.state;
  memo = data.memo;
  renderAll();
}

function renderAll() {
  if (!state) return;
  document.getElementById("week-label").textContent = state.week_label;
  const mb = document.getElementById("model-banner");
  if (state.model?.available) {
    mb.textContent = `DS MODEL: ${state.model.version}`;
    mb.classList.remove("hidden");
  } else {
    mb.classList.add("hidden");
  }
  renderBrief();
  renderAllocation();
  renderPerformance();
  renderExperiments();
  renderCreatives();
  renderData();
}

function renderBrief() {
  document.getElementById("brief-title").textContent = memo.title;
  document.getElementById("segment-context").textContent = memo.segment_context;
  document.getElementById("brief-bullets").innerHTML = memo.headline_bullets
    .map(b => `<div class="bullet-item">${b}</div>`).join("");
  document.getElementById("counterfactual").innerHTML =
    `<strong>Counterfactual:</strong> ${memo.counterfactual}`;
  document.getElementById("decisions-list").innerHTML = memo.decisions_pending
    .map(d => `
      <div class="decision-card">
        <h4>${d.title} <span class="status">${d.status}</span></h4>
        <p>${d.summary}</p>
        <ul>${d.details.map(x => `<li>${x}</li>`).join("")}</ul>
      </div>`).join("");
  document.getElementById("ledger-list").innerHTML = (state.ledger || [])
    .map(r => `<div class="ledger-item">
      <strong>${r.type}</strong> · ${r.timestamp?.slice(0, 16) || ""}
      ${r.summary || r.message || r.learning || ""}
      ${r.human_action ? ` → ${r.human_action}` : ""}
    </div>`).join("") || "<p class='muted'>No decisions logged yet.</p>";
}

function renderAllocation() {
  const a = state.allocation;
  document.getElementById("alloc-summary").innerHTML =
    `<h3>Recommendation</h3><p>${a.summary}</p><p class="muted">${a.method}</p>`;
  const tbody = document.querySelector("#alloc-table tbody");
  tbody.innerHTML = a.rationale.map(r => `
    <tr>
      <td>${r.label}</td>
      <td>$${r.current_spend.toLocaleString()}</td>
      <td>$${r.recommended_spend.toLocaleString()}</td>
      <td class="${r.delta >= 0 ? "delta-pos" : "delta-neg"}">${r.delta >= 0 ? "+" : ""}${r.delta.toLocaleString()}</td>
      <td>$${r.cac}</td>
      <td>${r.ltv_multiplier}×</td>
      <td style="font-size:0.8rem;color:var(--muted)">${r.score_plain}</td>
    </tr>`).join("");
}

function renderPerformance() {
  const kpis = state.kpis;
  const kpiHtml = [
    ["Spend", kpis.spend.value, kpis.spend.fmt_wow, false],
    ["Net-new conv", Math.round(kpis.new_conversions.value), kpis.new_conversions.fmt_wow, false],
    ["CAC", `$${Math.round(kpis.cac.value)}`, kpis.cac.fmt_wow, true],
    ["LTV:CAC", kpis.ltv_cac.value.toFixed(1) + "×", kpis.ltv_cac.fmt_wow, false],
    ["Payback", kpis.payback_months.value.toFixed(1) + "mo", kpis.payback_months.fmt_wow, true],
    ["Net-new %", (kpis.net_new_pct.value * 100).toFixed(0) + "%", kpis.net_new_pct.fmt_wow, false],
  ].map(([label, val, wow, inv]) => `
    <div class="kpi">
      <div class="label">${label}</div>
      <div class="value">${typeof val === "number" ? val.toLocaleString() : val}</div>
      <div class="delta">${wow || "—"} WoW</div>
    </div>`).join("");
  document.getElementById("kpi-row").innerHTML = kpiHtml;

  document.getElementById("alerts-box").innerHTML = (state.alerts || [])
    .map(a => `<div class="alert alert-${a.severity}"><strong>${a.title}</strong> — ${a.message}</div>`)
    .join("") || "<p class='muted'>No alerts this week.</p>";

  document.querySelector("#channel-table tbody").innerHTML = state.channels
    .map(c => `<tr>
      <td>${c.label}</td>
      <td>$${c.spend.toLocaleString()}</td>
      <td>${c.new_conversions}</td>
      <td>$${c.cac}</td>
      <td>${c.cac_wow?.pct != null ? (c.cac_wow.pct * 100).toFixed(1) + "%" : "—"}</td>
    </tr>`).join("");

  document.querySelector("#geo-table tbody").innerHTML = state.geo
    .map(g => `<tr>
      <td>${g.geo}</td>
      <td>$${g.spend.toLocaleString()}</td>
      <td>${g.new_conversions}</td>
      <td>$${g.cac}</td>
      <td>${g.arpu_multiplier}×</td>
      <td class="flag">${g.flag || ""}</td>
    </tr>`).join("");

  const attr = state.attribution;
  document.getElementById("attribution-box").innerHTML = `
    <h3>${attr.headline || "Attribution"}</h3>
    <p class="muted">${attr.simple_explanation || ""}</p>
    <p><strong>Key diagnostic:</strong> ${attr.retargeting_diagnostic?.plain_english || ""}</p>
    <p class="muted">${attr.action || ""}</p>`;
}

function renderExperiments() {
  document.getElementById("experiments-list").innerHTML = (state.experiments || [])
    .map(e => `
      <div class="exp-card">
        <span class="exp-badge ${e.type === "geo_holdout" ? "badge-holdout" : "badge-ab"}">${e.type === "geo_holdout" ? "GEO HOLDOUT" : "A/B TEST"}</span>
        <h3>${e.name}</h3>
        <p class="muted">${e.hypothesis}</p>
        <p>${e.plain_english}</p>
        <p>Control ${e.control_rate}% vs Variant ${e.variant_rate}% · Lift ${e.lift_pct}% · p=${e.p_value}</p>
        <p class="rec-${e.recommendation}">→ ${e.recommendation_text}</p>
        ${e.learning ? `<p><strong>Learning:</strong> ${e.learning}</p>` : ""}
      </div>`).join("") || "<p class='muted'>No experiments for this segment.</p>";
}

function renderCreatives() {
  document.getElementById("insight-cards").innerHTML = (state.creative_cards || [])
    .map(c => `
      <div class="insight-card fatigue-${c.fatigue}">
        <span class="fatigue-pill">${c.fatigue} fatigue</span>
        <h3>${c.name}</h3>
        <p class="muted">${c.channel_label} · Directive: ${c.directive_text}</p>
        <p><strong>Finding:</strong> ${c.finding}</p>
        <p><strong>Hypothesis:</strong> ${c.hypothesis}</p>
        <p><strong>Recommend:</strong> ${c.recommend_to_brand}</p>
        <div class="handoff">→ Insight Card for Brand (we test; Brand owns copy)</div>
      </div>`).join("");
}

function renderData() {
  const ds = state.data_source;
  const m = state.model || {};
  document.getElementById("data-status").innerHTML = `
    <p><strong>Warehouse:</strong> ${ds.label}</p>
    <p><strong>Path:</strong> ${ds.path}</p>
    <p><strong>Connected:</strong> ${ds.connected ? "Yes (sample fixtures)" : "No"}</p>`;
  document.getElementById("model-status").innerHTML = m.available
    ? `<p><strong>Active model:</strong> ${m.version}</p>
       <p><strong>Source:</strong> ${m.source}</p>
       <p><strong>Scored at:</strong> ${m.scored_at || "—"}</p>
       <p><strong>Allocator:</strong> Uses DS efficiency_score when confidence ≥ 50%; heuristic fallback otherwise.</p>`
    : `<p><strong>Model:</strong> Not available for this week — allocator uses heuristic (net-new/$ × LTV).</p>
       <p class="muted">DS team publishes to <code>ml_channel_scores</code> weekly.</p>`;
}

// Tabs
document.getElementById("tabs").addEventListener("click", e => {
  if (e.target.tagName !== "BUTTON") return;
  document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  e.target.classList.add("active");
  document.getElementById(`tab-${e.target.dataset.tab}`).classList.add("active");
});

// Segment toggle
document.getElementById("segment-toggle").addEventListener("click", e => {
  if (e.target.tagName !== "BUTTON") return;
  segment = e.target.dataset.segment;
  document.querySelectorAll(".segment-toggle button").forEach(b => b.classList.remove("active"));
  e.target.classList.add("active");
  loadState();
});

// Ask
document.getElementById("ask-btn").addEventListener("click", async () => {
  const q = document.getElementById("ask-input").value.trim();
  if (!q) return;
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q, segment }),
  });
  const data = await res.json();
  const el = document.getElementById("ask-result");
  el.classList.remove("hidden");
  el.innerHTML = `<p>${data.answer}</p><p class="sources">Sources: ${(data.sources || []).join(", ")}</p>`;
});

document.getElementById("ask-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("ask-btn").click();
});

// Approve allocation
document.getElementById("approve-alloc").addEventListener("click", async () => {
  const res = await fetch("/api/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segment, decision_id: "alloc_main", action: "approved" }),
  });
  const data = await res.json();
  if (data.ok) {
    alert("Allocation recommendation approved and logged to decision ledger.");
    loadState();
  }
});

document.getElementById("resync-btn")?.addEventListener("click", async () => {
  await fetch("/api/sync", { method: "POST" });
  loadState();
});

loadState();
