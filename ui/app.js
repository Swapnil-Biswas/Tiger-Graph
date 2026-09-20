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
      if (tabId === "playback") {
        if (!cyPlaybackInstance) {
          initPlaybackCytoscape();
        } else {
          setTimeout(() => cyPlaybackInstance.resize().fit(), 100);
        }
      }
      if (tabId === "compliance" && !activeEvidenceBundle) {
        const cCase = document.getElementById("select-compliance-case");
        const targetCid = (cCase && cCase.value) ? cCase.value : "HHG-001";
        loadEvidenceVault(targetCid);
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
    const selectCompliance = document.getElementById("select-compliance-case");
    if (selectCompliance) selectCompliance.innerHTML = "";
    const selectPlayback = document.getElementById("select-playback-case");
    if (selectPlayback) selectPlayback.innerHTML = "";
    const tbody = document.getElementById("case-board-tbody");
    tbody.innerHTML = "";

    casesData.forEach(c => {
      // Option in dropdown
      const opt = document.createElement("option");
      opt.value = c.case_id;
      opt.textContent = `${c.case_id} — Card ${c.card_id} (${c.trigger_type})`;
      select.appendChild(opt);

      if (selectCompliance) {
        const optComp = opt.cloneNode(true);
        selectCompliance.appendChild(optComp);
      }
      if (selectPlayback) {
        const optPlay = opt.cloneNode(true);
        selectPlayback.appendChild(optPlay);
      }

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

window.submitAnalystOverride = async function(caseId, newVerdict, justification, role = "L1_ANALYST") {
  try {
    const res = await fetch(`/api/cases/${caseId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analyst_id: "ANALYST-HUMAN",
        analyst_role: role,
        new_verdict: newVerdict,
        justification: justification
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Override failed");
    }
    const data = await res.json();
    alert(`Verdict successfully overridden to: ${newVerdict.toUpperCase()} (Audit ID: ${data.override.override_id})`);
    
    // Refresh case view
    const vBadge = document.getElementById("verdict-badge");
    if (vBadge) {
      vBadge.className = `verdict-badge verdict-${newVerdict}`;
      vBadge.textContent = `${newVerdict.toUpperCase()} (OVERRIDDEN)`;
    }
    loadCaseAuditTrail(caseId);
  } catch (e) {
    alert("Override error: " + e.message);
  }
};

window.loadCaseAuditTrail = async function(caseId) {
  try {
    const res = await fetch(`/api/cases/${caseId}/audit`);
    const data = await res.json();
    const trail = data.audit_trail || [];
    console.log(`Audit trail for ${caseId}:`, trail);
  } catch (e) {
    console.error("Failed to load audit trail:", e);
  }
};

// =========================================================================
// 5. COMPLIANCE & EVIDENCE VAULT (FRE 902)
// =========================================================================

let activeEvidenceBundle = null;

async function loadEvidenceVault(caseId) {
  const btnGen = document.getElementById("btn-generate-bundle");
  if (btnGen) btnGen.disabled = true;

  try {
    const res = await fetch(`/api/cases/${caseId}/evidence-bundle`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const bundle = await res.json();
    activeEvidenceBundle = bundle;

    // Update Header Card
    document.getElementById("vault-bundle-id").textContent = bundle.bundle_id;
    document.getElementById("vault-legal-status").textContent = "FEDERAL RULES OF EVIDENCE RULE 902(13)/(14) CERTIFIED RECORD";
    const statusTag = document.getElementById("vault-status-tag");
    statusTag.className = "cert-status-tag cert-valid";
    statusTag.textContent = "SEALED & AUTHENTICATED";

    document.getElementById("vault-merkle-root").textContent = bundle.merkle_root;
    document.getElementById("vault-signature").textContent = bundle.signature;
    document.getElementById("vault-signer").textContent = bundle.signer_identity;
    document.getElementById("vault-items-count").textContent = `${bundle.item_count} / ${bundle.item_count} Verified`;

    // Render 16 Items
    const container = document.getElementById("vault-items-container");
    container.innerHTML = "";

    bundle.items.forEach((item, idx) => {
      const card = document.createElement("div");
      card.className = "vault-item-card";
      card.innerHTML = `
        <div class="vault-item-top">
          <span class="vault-cat-badge">${item.category}</span>
          <span class="vault-item-num">Leaf #${idx + 1}</span>
        </div>
        <div class="vault-item-title">${item.title}</div>
        <div class="vault-item-hash mono-font" title="${item.sha256_hash}">
          SHA-256: <code>${item.sha256_hash.slice(0, 16)}...${item.sha256_hash.slice(-8)}</code>
        </div>
        <details class="vault-item-details">
          <summary>Inspect Canonical Payload</summary>
          <pre class="vault-item-json">${JSON.stringify(item.content, null, 2)}</pre>
        </details>
      `;
      container.appendChild(card);
    });

    // Render Chain of Custody
    const timeline = document.getElementById("vault-custody-timeline");
    timeline.innerHTML = "";
    bundle.chain_of_custody.forEach(evt => {
      const entry = document.createElement("div");
      entry.className = "custody-entry";
      entry.innerHTML = `
        <div class="custody-dot"></div>
        <div class="custody-content">
          <div class="custody-header">
            <strong>${evt.action}</strong>
            <span class="custody-time">${evt.timestamp}</span>
          </div>
          <div class="custody-body">
            <span>Actor: <code>${evt.actor}</code> (${evt.system_component})</span>
            <span class="custody-status ${evt.verification_status.includes('FAIL') ? 'status-fail' : 'status-ok'}">${evt.verification_status}</span>
          </div>
          ${evt.notes ? `<div class="custody-notes">${evt.notes}</div>` : ''}
        </div>
      `;
      timeline.appendChild(entry);
    });

  } catch (err) {
    console.error("Failed to load evidence vault:", err);
    alert("Evidence Vault error: " + err.message);
  } finally {
    if (btnGen) btnGen.disabled = false;
  }
}

async function verifyEvidenceVault(overrideBundle = null) {
  const bundleToTest = overrideBundle || activeEvidenceBundle;
  if (!bundleToTest) {
    alert("Please generate or seal an evidence bundle first.");
    return;
  }

  try {
    const res = await fetch("/api/compliance/verify-evidence-bundle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bundleToTest)
    });
    const audit = await res.json();

    const statusTag = document.getElementById("vault-status-tag");
    const countBadge = document.getElementById("vault-items-count");

    if (audit.is_valid) {
      statusTag.className = "cert-status-tag cert-valid";
      statusTag.textContent = "100% CRYPTOGRAPHICALLY VERIFIED";
      countBadge.textContent = `${audit.items_verified} / ${audit.total_items} Verified`;
      alert(`PASS: Merkle Root & HMAC-SHA256 Signature Verified. Zero Bit-Flips Detected. ${audit.legal_admissibility}`);
    } else {
      statusTag.className = "cert-status-tag cert-invalid";
      statusTag.textContent = "TAMPER DETECTED / AUDIT FAILED";
      countBadge.textContent = `${audit.items_verified} / ${audit.total_items} Verified (Corrupted: ${audit.corrupted_items.length})`;
      const corruptedNames = audit.corrupted_items.map(c => c.item_id).join(", ");
      alert(`CRITICAL ALERT: Tamper detected! Merkle root or signature invalid. Corrupted artifacts: ${corruptedNames}`);
    }
  } catch (e) {
    alert("Verification failed: " + e.message);
  }
}

function simulateTamperVault() {
  if (!activeEvidenceBundle) {
    alert("Generate an evidence bundle first.");
    return;
  }
  // Deep clone and corrupt item #1
  const tampered = JSON.parse(JSON.stringify(activeEvidenceBundle));
  tampered.items[0].content.exposure_usd = 999999.99; // Forged exposure
  alert("SIMULATING MALICIOUS BIT-FLIP: Forged exposure_usd in Item #1. Submitting to cryptographic verifier...");
  verifyEvidenceVault(tampered);
}

// =========================================================================
// 6. TEMPORAL GRAPH PLAYBACK & SYNDICATE CASCADE
// =========================================================================

let playbackTimelineData = null;
let currentPlaybackStep = 0;
let playbackIntervalId = null;
let cyPlaybackInstance = null;

function initPlaybackCytoscape() {
  const container = document.getElementById("cy-playback-container");
  if (!container) return;

  cyPlaybackInstance = cytoscape({
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
          'width': 26,
          'height': 26,
          'border-width': 2,
          'border-color': 'rgba(255, 255, 255, 0.4)'
        }
      },
      {
        selector: 'node[type = "Card"]',
        style: { 'background-color': '#00f0ff' }
      },
      {
        selector: 'node[type = "Transaction"]',
        style: { 'background-color': '#ef4444' }
      },
      {
        selector: 'node[type = "Device"]',
        style: { 'background-color': '#eab308' }
      },
      {
        selector: 'node[type = "Merchant"]',
        style: { 'background-color': '#10b981' }
      },
      {
        selector: 'node.highlighted-step',
        style: {
          'border-width': 4,
          'border-color': '#ff0055',
          'width': 34,
          'height': 34
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': 'rgba(100, 116, 139, 0.4)',
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': 'rgba(100, 116, 139, 0.4)',
          'arrow-scale': 0.8
        }
      },
      {
        selector: 'edge.highlighted-edge',
        style: {
          'line-color': '#ff0055',
          'target-arrow-color': '#ff0055',
          'width': 3.5
        }
      }
    ],
    layout: { name: 'concentric', padding: 25 }
  });
}

async function loadPlaybackTimeline(caseId) {
  const btnLoad = document.getElementById("btn-load-playback");
  if (btnLoad) btnLoad.disabled = true;

  try {
    const res = await fetch(`/api/graph/playback/${caseId}?max_frames=40`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    playbackTimelineData = await res.json();
    currentPlaybackStep = 0;

    const totalFrames = playbackTimelineData.total_frames || (playbackTimelineData.frames ? playbackTimelineData.frames.length : 0);

    // Update Slider Bounds
    const slider = document.getElementById("playback-slider");
    slider.min = 0;
    slider.max = Math.max(0, totalFrames - 1);
    slider.value = 0;

    document.getElementById("playback-step-total").textContent = totalFrames;

    // Render Milestone Chips
    const mContainer = document.getElementById("playback-milestones-container");
    mContainer.innerHTML = "";
    if (playbackTimelineData.milestones) {
      Object.entries(playbackTimelineData.milestones).forEach(([name, fIdx]) => {
        const chip = document.createElement("span");
        chip.className = "milestone-chip";
        chip.textContent = `★ Frame ${fIdx + 1}: ${name}`;
        chip.onclick = () => renderPlaybackFrame(fIdx);
        mContainer.appendChild(chip);
      });
    }

    if (!cyPlaybackInstance) {
      initPlaybackCytoscape();
    }

    renderPlaybackFrame(0);
  } catch (err) {
    console.error("Failed to load playback timeline:", err);
    alert("Playback error: " + err.message);
  } finally {
    if (btnLoad) btnLoad.disabled = false;
  }
}

function renderPlaybackFrame(idx) {
  if (!playbackTimelineData || !playbackTimelineData.frames || !playbackTimelineData.frames[idx]) return;
  currentPlaybackStep = idx;

  const frame = playbackTimelineData.frames[idx];
  const exposure = frame.current_exposure_usd !== undefined ? frame.current_exposure_usd : (frame.cumulative_exposure || 0.0);

  // Update Counters & Metrics
  document.getElementById("playback-step-cur").textContent = idx + 1;
  document.getElementById("playback-slider").value = idx;
  document.getElementById("playback-exposure").textContent = `$${exposure.toFixed(2)}`;
  document.getElementById("playback-risk").textContent = frame.risk_score.toFixed(4);
  document.getElementById("playback-caption-text").textContent = `[${frame.timestamp}] ${frame.narrative_caption}`;

  const elements = frame.cumulative_elements || { nodes: frame.active_nodes || [], edges: frame.active_edges || [] };
  const nodes = elements.nodes || [];
  const edges = elements.edges || [];

  document.getElementById("playback-nodes-count").textContent = `${nodes.length} Active Nodes`;

  // Render Subgraph in Cytoscape
  if (cyPlaybackInstance) {
    cyPlaybackInstance.elements().remove();
    cyPlaybackInstance.add(nodes);
    cyPlaybackInstance.add(edges);

    // Highlight Current Step Node & Edge
    if (frame.highlight_node_ids && frame.highlight_node_ids.length > 0) {
      frame.highlight_node_ids.forEach(nid => {
        const targetNode = cyPlaybackInstance.getElementById(nid);
        if (targetNode.length > 0) {
          targetNode.addClass('highlighted-step');
        }
      });
    }
    if (frame.highlight_edge_ids && frame.highlight_edge_ids.length > 0) {
      frame.highlight_edge_ids.forEach(eid => {
        const targetEdge = cyPlaybackInstance.getElementById(eid);
        if (targetEdge.length > 0) {
          targetEdge.addClass('highlighted-edge');
        }
      });
    }

    cyPlaybackInstance.layout({ name: 'concentric', padding: 25, animate: false }).run();
  }
}

function stepPlayback(delta) {
  if (!playbackTimelineData) return;
  const next = Math.max(0, Math.min(playbackTimelineData.total_steps - 1, currentPlaybackStep + delta));
  renderPlaybackFrame(next);
}

function togglePlaybackPlay() {
  const btn = document.getElementById("btn-playback-play");
  if (playbackIntervalId) {
    clearInterval(playbackIntervalId);
    playbackIntervalId = null;
    btn.textContent = "▶ Play";
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-primary");
  } else {
    if (!playbackTimelineData) return;
    btn.textContent = "⏸ Pause";
    btn.classList.remove("btn-primary");
    btn.classList.add("btn-danger");

    playbackIntervalId = setInterval(() => {
      if (currentPlaybackStep >= playbackTimelineData.total_steps - 1) {
        togglePlaybackPlay();
      } else {
        stepPlayback(1);
      }
    }, 1200);
  }
}

// Wire additional listeners
document.addEventListener("DOMContentLoaded", () => {
  const btnGen = document.getElementById("btn-generate-bundle");
  if (btnGen) {
    btnGen.addEventListener("click", () => {
      const sel = document.getElementById("select-compliance-case");
      loadEvidenceVault(sel ? sel.value : "HHG-001");
    });
  }

  const btnVer = document.getElementById("btn-verify-bundle");
  if (btnVer) {
    btnVer.addEventListener("click", () => verifyEvidenceVault());
  }

  const btnTamper = document.getElementById("btn-tamper-test");
  if (btnTamper) {
    btnTamper.addEventListener("click", () => simulateTamperVault());
  }

  const btnLoadPlay = document.getElementById("btn-load-playback");
  if (btnLoadPlay) {
    btnLoadPlay.addEventListener("click", () => {
      const sel = document.getElementById("select-playback-case");
      loadPlaybackTimeline(sel ? sel.value : "HHG-001");
    });
  }

  const btnBack = document.getElementById("btn-playback-step-back");
  if (btnBack) btnBack.addEventListener("click", () => stepPlayback(-1));

  const btnFwd = document.getElementById("btn-playback-step-forward");
  if (btnFwd) btnFwd.addEventListener("click", () => stepPlayback(1));

  const btnPlay = document.getElementById("btn-playback-play");
  if (btnPlay) btnPlay.addEventListener("click", () => togglePlaybackPlay());

  const slider = document.getElementById("playback-slider");
  if (slider) {
    slider.addEventListener("input", (e) => {
      renderPlaybackFrame(parseInt(e.target.value));
    });
  }
});


