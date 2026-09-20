// TigerGraph Fraud Investigator — Frontend Application Logic

let cyInstance = null;
let currentCaseId = "HHG-001";
let casesData = [];

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initCytoscape();
  loadCasesList();
  loadApprovals();
  setupEventListeners();
});

// Tab Navigation
function initTabs() {
  const tabs = document.querySelectorAll(".nav-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-view").forEach(v => v.classList.remove("active"));
      
      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const targetView = document.getElementById(`view-${tabId}`);
      if (targetView) targetView.classList.add("active");

      if (tabId === "investigate" && cyInstance) {
        setTimeout(() => cyInstance.resize().fit(), 100);
      }
    });
  });
}

// Cytoscape Subgraph Initialization
function initCytoscape() {
  const container = document.getElementById("cy-container");
  if (!container) return;

  cyInstance = cytoscape({
    container: container,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'color': '#f0f4fc',
          'font-size': '10px',
          'font-family': 'JetBrains Mono, monospace',
          'text-valign': 'bottom',
          'text-margin-y': 5,
          'background-color': '#00f0ff',
          'width': 28,
          'height': 28,
          'border-width': 2,
          'border-color': 'rgba(255, 255, 255, 0.4)',
          'transition-property': 'background-color, border-color, width, height, opacity',
          'transition-duration': '0.2s'
        }
      },
      {
        selector: 'node[type = "Case"]',
        style: {
          'shape': 'octagon',
          'background-color': '#ec4899',
          'border-color': '#f472b6',
          'border-width': 3,
          'width': 36,
          'height': 36
        }
      },
      {
        selector: 'node[type = "Customer"]',
        style: {
          'shape': 'ellipse',
          'background-color': '#8b5cf6',
          'border-color': '#c084fc',
          'border-width': 2,
          'width': 32,
          'height': 32
        }
      },
      {
        selector: 'node[type = "Card"]',
        style: {
          'shape': 'round-rectangle',
          'background-color': '#0ea5e9',
          'border-color': '#38bdf8',
          'border-width': 2,
          'width': 42,
          'height': 24
        }
      },
      {
        selector: 'node[type = "Transaction"]',
        style: {
          'shape': 'hexagon',
          'background-color': '#ef4444',
          'border-color': '#f87171',
          'border-width': 2,
          'width': 34,
          'height': 34
        }
      },
      {
        selector: 'node[type = "DeviceProfile"]',
        style: {
          'shape': 'diamond',
          'background-color': '#f59e0b',
          'border-color': '#fbbf24',
          'border-width': 2,
          'width': 30,
          'height': 30
        }
      },
      {
        selector: 'node[type = "BillingRegion"]',
        style: {
          'shape': 'tag',
          'background-color': '#10b981',
          'border-color': '#34d399',
          'border-width': 2,
          'width': 30,
          'height': 24
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': 'rgba(255, 255, 255, 0.18)',
          'target-arrow-color': 'rgba(255, 255, 255, 0.35)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '8px',
          'color': '#8a99b5',
          'transition-property': 'line-color, width, opacity',
          'transition-duration': '0.2s'
        }
      },
      {
        selector: 'node.highlighted',
        style: {
          'border-color': '#00f0ff',
          'border-width': 4,
          'opacity': 1.0,
          'z-index': 99
        }
      },
      {
        selector: 'edge.highlighted',
        style: {
          'line-color': '#00f0ff',
          'target-arrow-color': '#00f0ff',
          'width': 3,
          'opacity': 1.0,
          'z-index': 99
        }
      },
      {
        selector: '.faded',
        style: {
          'opacity': 0.15
        }
      }
    ],
    layout: {
      name: 'concentric',
      padding: 25
    }
  });

  // Interactive Node Tap (Highlight Neighborhood & Update HUD)
  cyInstance.on('tap', 'node', function(evt) {
    const node = evt.target;
    const neighborhood = node.neighborhood().add(node);
    
    cyInstance.elements().removeClass('highlighted').addClass('faded');
    neighborhood.removeClass('faded').addClass('highlighted');
    
    // Update HUD Inspector
    const hud = document.getElementById("hud-text");
    if (hud) {
      const d = node.data();
      const connectedEdges = node.connectedEdges().length;
      const neighbors = node.neighborhood('node').map(n => n.data('label')).join(', ');
      hud.innerHTML = `<strong>[${d.type || 'Entity'}]</strong> ID: <code>${d.id}</code> | Degree: ${connectedEdges} connection(s)${neighbors ? ` -> Connected to: ${neighbors}` : ''}`;
    }
  });

  // Tap Canvas Background to Reset Highlighting
  cyInstance.on('tap', function(evt) {
    if (evt.target === cyInstance) {
      cyInstance.elements().removeClass('highlighted faded');
      const hud = document.getElementById("hud-text");
      if (hud) {
        hud.textContent = "Click any node to inspect incident relationships and neighborhood.";
      }
    }
  });

  // Graph Controls Event Listeners
  const btnConcentric = document.getElementById("btn-layout-concentric");
  if (btnConcentric) btnConcentric.addEventListener("click", () => cyInstance.layout({ name: 'concentric', padding: 25, animate: true }).run());
  
  const btnBreadth = document.getElementById("btn-layout-breadthfirst");
  if (btnBreadth) btnBreadth.addEventListener("click", () => cyInstance.layout({ name: 'breadthfirst', directed: true, padding: 25, animate: true }).run());

  const btnCose = document.getElementById("btn-layout-cose");
  if (btnCose) btnCose.addEventListener("click", () => cyInstance.layout({ name: 'cose', animate: true, padding: 25 }).run());

  const btnFit = document.getElementById("btn-cy-fit");
  if (btnFit) btnFit.addEventListener("click", () => cyInstance.animate({ fit: { padding: 30 }, duration: 400 }));
}

// Load List of Cases from Backend API
async function loadCasesList() {
  try {
    const res = await fetch("/api/cases");
    const data = await res.json();
    casesData = data.cases || [];

    const select = document.getElementById("select-case");
    select.innerHTML = "";
    const tbody = document.getElementById("case-board-tbody");
    tbody.innerHTML = "";

    casesData.forEach(c => {
      // Option in dropdown
      const opt = document.createElement("option");
      opt.value = c.case_id;
      opt.textContent = `${c.case_id} — Card ${c.card_id} (${c.trigger_type})`;
      select.appendChild(opt);

      // Table row in Case Board
      const tr = document.createElement("tr");
      const verdictClass = c.verdict === "fraud" ? "verdict-fraud" : (c.verdict === "legitimate" ? "verdict-legit" : "verdict-pending");
      tr.innerHTML = `
        <td><strong>${c.case_id}</strong></td>
        <td>${c.opened_at || '--'}</td>
        <td><span class="stat-pill">${c.trigger_type}</span></td>
        <td><code>${c.card_id}</code></td>
        <td>${c.customer_id}</td>
        <td>${c.risk_score !== null ? c.risk_score : '—'}</td>
        <td><span class="status-badge badge-idle">${c.status}</span></td>
        <td><span class="verdict-badge ${verdictClass}">${c.verdict.toUpperCase()}</span></td>
        <td>
          <button class="btn btn-secondary" onclick="selectAndInvestigate('${c.case_id}')">
            Investigate
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    if (casesData.length > 0) {
      currentCaseId = casesData[0].case_id;
      loadSubgraph(currentCaseId);
    }
  } catch (err) {
    console.error("Failed to load cases list:", err);
  }
}

// Load Subgraph for Cytoscape
async function loadSubgraph(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}/graph`);
    const data = await res.json();
    if (cyInstance && data.nodes) {
      cyInstance.elements().remove();
      cyInstance.add(data.nodes);
      cyInstance.add(data.edges);
      cyInstance.layout({ name: 'concentric', padding: 25 }).run();
    }
  } catch (err) {
    console.error("Failed to load subgraph:", err);
  }
}

// Event Listeners
function setupEventListeners() {
  const caseSelect = document.getElementById("select-case");
  caseSelect.addEventListener("change", (e) => {
    currentCaseId = e.target.value;
    loadSubgraph(currentCaseId);
  });

  const btnRun = document.getElementById("btn-run-investigation");
  btnRun.addEventListener("click", () => {
    runInvestigation(currentCaseId);
  });

  const btnExport = document.getElementById("btn-export-json");
  btnExport.addEventListener("click", () => {
    window.open(`/api/export/${currentCaseId}`, '_blank');
  });

  // 1-Click Interactive Demo Preset Buttons
  document.querySelectorAll(".preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const cid = btn.dataset.case;
      const scenario = btn.dataset.scenario;
      document.getElementById("select-case").value = cid;
      document.getElementById("select-scenario").value = scenario;
      currentCaseId = cid;
      loadSubgraph(currentCaseId);
      runInvestigation(cid);

      // Visual pulse on active preset button
      document.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active-preset"));
      btn.classList.add("active-preset");
    });
  });

  const btnRunAll = document.getElementById("btn-run-all-benchmark");
  if (btnRunAll) {
    btnRunAll.addEventListener("click", async () => {
      btnRunAll.disabled = true;
      btnRunAll.textContent = "Running Benchmark (20 Cases)...";
      try {
        const res = await fetch("/api/benchmark/run", { method: "POST" });
        const result = await res.json();
        alert(`Benchmark run complete! Evaluated ${result.total_evaluated} cases. Answer files generated in cases/`);
        loadCasesList();
      } catch (e) {
        alert("Error during benchmark run: " + e.message);
      } finally {
        btnRunAll.disabled = false;
        btnRunAll.textContent = "⚡ Run Full Benchmark (20 Cases)";
      }
    });
  }
}

window.selectAndInvestigate = function(caseId) {
  currentCaseId = caseId;
  const select = document.getElementById("select-case");
  if (select) select.value = caseId;
  document.getElementById("tab-investigate").click();
  runInvestigation(caseId);
};

// Run Live Investigation via SSE Streaming
function runInvestigation(caseId) {
  const scenario = document.getElementById("select-scenario").value;
  const timeline = document.getElementById("timeline-stream");
  const badge = document.getElementById("investigation-status-badge");
  
  timeline.innerHTML = "";
  badge.className = "status-badge badge-running";
  badge.textContent = "Investigating...";

  loadSubgraph(caseId);

  const eventSource = new EventSource(`/api/cases/${caseId}/stream?scenario=${encodeURIComponent(scenario)}`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    addTimelineStep(data.step, data.message || "");

    if (data.step === "ASSESS") {
      updateGauges(data.fraud_probability, 0.70);
      renderInitialActions(data.initial_actions || []);
    } else if (data.step === "DECIDE_ACTIONS") {
      renderFinalActions(data.final_actions || [], data.what_changed || "");
    } else if (data.step === "COMPLETE") {
      eventSource.close();
      badge.className = "status-badge badge-complete";
      badge.textContent = "Complete";
      renderCompleteCase(data.payload);
      loadApprovals();
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    badge.className = "status-badge badge-complete";
    badge.textContent = "Complete";
  };
}

function addTimelineStep(stepName, message) {
  const timeline = document.getElementById("timeline-stream");
  const div = document.createElement("div");
  div.className = "timeline-step active";

  const icons = {
    TRIGGER: "🎯",
    OPEN_CASE: "📂",
    BUDGET_PLAN: "📊",
    RETRIEVE_MEMORY: "🧠",
    INVESTIGATE: "🔍",
    GRAPHRAG_BM25: "📚",
    ASSESS: "⚖️",
    REQUEST_EVIDENCE: "💬",
    DECIDE_ACTIONS: "🛡️",
    SELF_CRITIQUE: "🔍",
    COMPLETE: "✅"
  };

  div.innerHTML = `
    <div class="step-icon">${icons[stepName] || "⚙️"}</div>
    <div class="step-content">
      <h4>${stepName}</h4>
      <p>${message}</p>
    </div>
  `;
  timeline.appendChild(div);
  timeline.scrollTop = timeline.scrollHeight;
}

// Update Circular Gauges
function updateGauges(prob, conf) {
  const riskPercent = Math.round(prob * 100);
  const confPercent = Math.round(conf * 100);

  document.getElementById("val-risk-score").textContent = `${riskPercent}`;
  document.getElementById("val-confidence").textContent = `${confPercent}%`;

  const riskCircle = document.querySelector("#svg-risk-gauge .circle-risk");
  const confCircle = document.querySelector("#svg-conf-gauge .circle-conf");

  if (riskCircle) riskCircle.setAttribute("stroke-dasharray", `${riskPercent}, 100`);
  if (confCircle) confCircle.setAttribute("stroke-dasharray", `${confPercent}, 100`);
}

function renderInitialActions(actions) {
  const container = document.getElementById("initial-actions-list");
  container.innerHTML = "";
  if (actions.length === 0) {
    container.innerHTML = "<p class='placeholder-text'>No initial actions</p>";
    return;
  }
  actions.forEach(a => {
    const div = document.createElement("div");
    div.className = "action-item";
    div.innerHTML = `
      <span class="route-badge route-${a.route}">${a.route}</span>
      <div>
        <strong>${a.action}</strong>
        <p style="font-size:0.75rem; color:var(--text-muted);">${a.reason}</p>
      </div>
    `;
    container.appendChild(div);
  });
}

function renderFinalActions(actions, whatChanged) {
  const container = document.getElementById("final-actions-list");
  container.innerHTML = "";
  if (actions.length === 0) {
    container.innerHTML = "<p class='placeholder-text'>No final actions</p>";
    return;
  }
  actions.forEach(a => {
    const div = document.createElement("div");
    div.className = "action-item";
    div.innerHTML = `
      <span class="route-badge route-${a.route}">${a.route}</span>
      <div>
        <strong>${a.action}</strong>
        <p style="font-size:0.75rem; color:var(--text-muted);">${a.reason}</p>
      </div>
    `;
    container.appendChild(div);
  });

  document.getElementById("what-changed-text").textContent = whatChanged || "No changes recorded.";
}

function renderCompleteCase(payload) {
  const c = payload.case;
  updateGauges(c.fraud_probability, 0.92);

  // Verdict badge
  const vBadge = document.getElementById("verdict-badge");
  vBadge.className = `verdict-badge verdict-${c.verdict === "fraud" ? "fraud" : (c.verdict === "legitimate" ? "legit" : "uncertain")}`;
  vBadge.textContent = c.verdict.toUpperCase();

  document.getElementById("val-pattern").textContent = c.pattern;
  document.getElementById("val-exposure").textContent = `$${c.exposure_usd.toFixed(2)}`;
  document.getElementById("val-sufficiency").textContent = "Sufficient to Act";

  // Evidence list
  const evContainer = document.getElementById("evidence-list-container");
  evContainer.innerHTML = "";
  const evBadge = document.getElementById("evidence-count-badge");
  evBadge.textContent = `${c.evidence.length} items`;

  c.evidence.forEach(ev => {
    const div = document.createElement("div");
    div.className = "evidence-card";
    div.innerHTML = `
      <div class="evidence-meta">
        <span class="ev-id">${ev.id}</span>
        <span class="ev-ref">${ev.source} | ${ev.ref}</span>
      </div>
      <p>${ev.claim}</p>
    `;
    evContainer.appendChild(div);
  });
}

// Load Approvals Queue
async function loadApprovals() {
  try {
    const res = await fetch("/api/approvals");
    const data = await res.json();
    const approvals = data.approvals || [];
    
    document.getElementById("badge-approvals").textContent = approvals.length;
    const container = document.getElementById("approvals-list-container");
    container.innerHTML = "";

    if (approvals.length === 0) {
      container.innerHTML = "<p class='placeholder-text'>No pending actions requiring approval.</p>";
      return;
    }

    approvals.forEach(appr => {
      const div = document.createElement("div");
      div.className = "glass-card";
      div.innerHTML = `
        <div class="card-header">
          <h4>Case ${appr.case_id} — ${appr.action}</h4>
          <span class="route-badge route-${appr.route}">${appr.route} APPROVAL</span>
        </div>
        <p style="font-size:0.85rem; margin-bottom:0.75rem;">${appr.reason}</p>
        <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1rem;">Exposure: $${appr.exposure_usd.toFixed(2)}</p>
        <div style="display:flex; gap:0.5rem;">
          <button class="btn btn-primary" onclick="handleApproval('${appr.approval_id}', 'approved')">Approve Action</button>
          <button class="btn btn-secondary" onclick="handleApproval('${appr.approval_id}', 'rejected')">Reject</button>
        </div>
      `;
      container.appendChild(div);
    });
  } catch (e) {
    console.error("Failed to load approvals:", e);
  }
}

window.handleApproval = async function(approvalId, decision) {
  try {
    await fetch(`/api/approvals/${approvalId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: approvalId, decision: decision })
    });
    alert(`Action ${decision} successfully!`);
    loadApprovals();
  } catch (e) {
    alert("Approval error: " + e.message);
  }
};
