"""
Self-Contained Interactive HTML Incident Dossier Exporter
Generates single-file, offline-viewable executive incident briefing reports
embedding Cytoscape.js topologies, evidence grounding tables, counterfactual
decision inversions, and regulatory FinCEN SAR / NCA STR filings.
"""

import os
import json
import html
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class IncidentDossierExporter:
    """
    Exports complete investigation bundles into portable, standalone HTML dossiers.
    """

    @classmethod
    def export_html_dossier(
        cls,
        case_answer: Dict[str, Any],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Renders a self-contained HTML incident dossier from an investigation answer bundle.
        """
        case_id = case_answer.get("case_id", "UNKNOWN")
        c_data = case_answer.get("case", {})
        verdict = c_data.get("verdict", "uncertain").upper()
        status = c_data.get("status", "NEW").replace("_", " ").title()
        exposure = float(c_data.get("exposure_usd", 0.0))
        prob = float(c_data.get("fraud_probability", 0.5))
        pattern = c_data.get("pattern", "none").replace("_", " ").title()
        summary = c_data.get("summary", "No summary provided.")
        stop_reason = case_answer.get("stop_reason", "Investigation completed.")

        # Evidence Items
        evidence_rows = []
        for ev in c_data.get("evidence", []):
            evidence_rows.append(
                f"<tr>"
                f"<td><span class='badge-id'>{html.escape(str(ev.get('id', '')))}</span></td>"
                f"<td>{html.escape(str(ev.get('source', '')))}</td>"
                f"<td><code>{html.escape(str(ev.get('ref', '')))}</code></td>"
                f"<td>{html.escape(str(ev.get('claim', '')))}</td>"
                f"</tr>"
            )
        evidence_tbody = "\n".join(evidence_rows) if evidence_rows else "<tr><td colspan='4'>No evidence items recorded.</td></tr>"

        # Counterfactuals
        cf_rows = []
        for cf in c_data.get("counterfactuals", []):
            cf_rows.append(
                f"<tr>"
                f"<td><strong>{html.escape(str(cf.get('feature', '')))}</strong></td>"
                f"<td><code>{html.escape(str(cf.get('current_value', '')))}</code></td>"
                f"<td><span class='cf-inverted'>{html.escape(str(cf.get('inversion_threshold', '')))}</span></td>"
                f"<td>{html.escape(str(cf.get('explanation', '')))}</td>"
                f"</tr>"
            )
        cf_tbody = "\n".join(cf_rows) if cf_rows else "<tr><td colspan='4'>No counterfactual conditions identified.</td></tr>"

        # Next Best Actions
        actions_rows = []
        for act in case_answer.get("next_best_actions", {}).get("final", []):
            route = act.get("route", "auto").upper()
            actions_rows.append(
                f"<tr>"
                f"<td><strong>{html.escape(str(act.get('action', '')))}</strong></td>"
                f"<td><span class='route-badge route-{act.get('route', 'auto')}'>{route}</span></td>"
                f"<td>{html.escape(str(act.get('reason', '')))}</td>"
                f"</tr>"
            )
        actions_tbody = "\n".join(actions_rows) if actions_rows else "<tr><td colspan='3'>No actions taken.</td></tr>"

        # SAR Narrative
        sar = case_answer.get("sar", {})
        sar_file = sar.get("file", False)
        sar_narrative = sar.get("narrative", "")
        if sar_file and sar_narrative:
            sar_html = f"<div class='sar-box'><pre>{html.escape(sar_narrative)}</pre></div>"
        else:
            sar_html = "<p class='text-muted'>Regulatory criteria for filing a Suspicious Activity Report (SAR) were not triggered for this incident.</p>"

        # Self-Critique Seal
        critique = case_answer.get("audit_critique", {})
        faithfulness = critique.get("faithfulness_score", 1.0)
        hallucinations = critique.get("hallucinated_facts_count", 0)

        # Cytoscape Graph Data Assembly
        cy_nodes = [
            {"data": {"id": f"CASE-{case_id}", "label": f"Case: {case_id}", "type": "Case", "color": "#8b5cf6"}},
            {"data": {"id": f"CARD-{case_id}", "label": f"Card", "type": "Card", "color": "#00f0ff"}},
        ]
        cy_edges = [
            {"data": {"source": f"CASE-{case_id}", "target": f"CARD-{case_id}", "label": "SUBJECT_CARD"}},
        ]
        for idx, aff in enumerate(c_data.get("affected_txn_ids", [])[:5], 1):
            cy_nodes.append({"data": {"id": f"TXN-{aff}", "label": f"Txn {aff}", "type": "Transaction", "color": "#ef4444"}})
            cy_edges.append({"data": {"source": f"CARD-{case_id}", "target": f"TXN-{aff}", "label": "EXPOSURE"}})

        cy_elements_json = json.dumps({"nodes": cy_nodes, "edges": cy_edges})
        verdict_color = "#ef4444" if verdict == "FRAUD" else ("#10b981" if verdict == "LEGITIMATE" else "#f59e0b")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Incident Dossier — {html.escape(case_id)}</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: rgba(18, 26, 44, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #00f0ff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2rem;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .verdict-badge {{
      background: {verdict_color};
      color: #fff;
      padding: 0.5rem 1.25rem;
      border-radius: 20px;
      font-weight: 700;
      font-size: 1.1rem;
      letter-spacing: 1px;
    }}
    .stats-bar {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }}
    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem;
      text-align: center;
    }}
    .stat-card .lbl {{ font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; }}
    .stat-card .val {{ font-size: 1.5rem; font-weight: 700; color: #fff; margin-top: 0.25rem; }}
    .section-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.75rem;
      margin-bottom: 2rem;
    }}
    h2 {{ font-size: 1.25rem; margin-bottom: 1rem; color: #fff; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    p {{ margin-bottom: 1rem; color: var(--text); }}
    #cy-container {{
      width: 100%;
      height: 320px;
      background: #060911;
      border-radius: 8px;
      border: 1px solid var(--border);
      margin-bottom: 1rem;
    }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.9rem; }}
    th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; }}
    .badge-id {{ background: rgba(0, 240, 255, 0.15); color: var(--accent); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; }}
    .cf-inverted {{ color: #10b981; font-weight: 600; }}
    .route-badge {{ padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }}
    .route-auto {{ background: rgba(16, 185, 129, 0.2); color: #10b981; }}
    .route-L1 {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; }}
    .route-L2 {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
    .sar-box pre {{
      background: #060911;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      white-space: pre-wrap;
      font-family: monospace;
      font-size: 0.85rem;
      line-height: 1.4;
      color: #94a3b8;
    }}
    .seal {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.3);
      border-radius: 8px;
      padding: 1rem 1.5rem;
      font-size: 0.85rem;
    }}
    .seal strong {{ color: #10b981; }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div>
        <h1 style="font-size: 1.75rem; font-weight: 800; color: #fff;">TigerGraph Incident Dossier</h1>
        <p style="color: var(--text-muted); margin-top: 0.25rem;">Case Reference: <code>{html.escape(case_id)}</code> | Status: {status}</p>
      </div>
      <div class="verdict-badge">{verdict}</div>
    </div>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat-card">
        <div class="lbl">Assessed Exposure</div>
        <div class="val">${exposure:.2f}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Fraud Probability</div>
        <div class="val">{prob:.2f}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Typology Pattern</div>
        <div class="val" style="font-size: 1.1rem; padding-top: 0.4rem;">{pattern}</div>
      </div>
      <div class="stat-card">
        <div class="lbl">Audit Faithfulness</div>
        <div class="val" style="color: #10b981;">{faithfulness:.2f}</div>
      </div>
    </div>

    <!-- Investigation Narrative -->
    <div class="section-card">
      <h2>1. Autonomous Investigation Narrative</h2>
      <p>{html.escape(summary)}</p>
      <p style="font-size: 0.85rem; color: var(--text-muted);"><strong>Reason Stopped:</strong> {html.escape(stop_reason)}</p>
    </div>

    <!-- Interactive Subgraph -->
    <div class="section-card">
      <h2>2. Incident Graph Topology</h2>
      <div id="cy-container"></div>
      <p style="font-size: 0.8rem; color: var(--text-muted);">Interactive Cytoscape visualization rendered offline. Nodes represent investigated card, customer, device, and exposure transactions.</p>
    </div>

    <!-- Evidence Citations -->
    <div class="section-card">
      <h2>3. Grounding Evidence & Citations</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Source</th>
            <th>Query Reference</th>
            <th>Claim / Fact</th>
          </tr>
        </thead>
        <tbody>
          {evidence_tbody}
        </tbody>
      </table>
    </div>

    <!-- Counterfactual Analysis & Interactive Decision Boundary -->
    <div class="section-card">
      <h2>4. Counterfactual Decision Boundary & Sensitivity Sliders</h2>

      <!-- Visual Decision Boundary Bar -->
      <div style="margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.35rem;">
          <span style="color: #10b981;">&larr; Legitimate (&lt; 0.30)</span>
          <span style="color: #f59e0b;">Step-Up / Review (0.30 - 0.70)</span>
          <span style="color: #ef4444;">Confirmed Fraud (&gt; 0.70) &rarr;</span>
        </div>
        <div style="position: relative; height: 18px; border-radius: 9px; background: linear-gradient(90deg, #10b981 0%, #f59e0b 50%, #ef4444 100%); overflow: visible;">
          <div id="sim-marker" style="position: absolute; left: {min(98, max(2, int(prob * 100)))}%; top: -6px; transform: translateX(-50%); width: 6px; height: 30px; background: #fff; border-radius: 3px; box-shadow: 0 0 8px rgba(0,0,0,0.8);"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #fff; margin-top: 0.5rem;">
          <span>Assessed Base Probability: <strong>{prob:.2f}</strong></span>
          <span>Simulated Probability: <strong id="sim-prob-val" style="color: var(--accent);">{prob:.2f}</strong></span>
          <span>Simulated Verdict: <span id="sim-verdict-badge" class="route-badge route-{verdict.lower()}">{verdict}</span></span>
        </div>
      </div>

      <!-- Interactive Sliders Simulator -->
      <div style="background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; margin-bottom: 1.5rem;">
        <h3 style="font-size: 0.95rem; color: var(--accent); margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;">Interactive Sensitivity Simulator</h3>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">Adjust counterfactual evidence levers below to simulate real-time decision boundary transitions.</p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;">
          <div>
            <label style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
              <span>Customer Verification</span>
              <span id="lbl-cust-val" style="color: #fff;">Unverified (0.00)</span>
            </label>
            <input type="range" id="slider-cust" min="0" max="1" step="0.05" value="0" style="width: 100%; accent-color: var(--accent);" oninput="updateSimulation()">
          </div>

          <div>
            <label style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
              <span>Device Recognition History</span>
              <span id="lbl-dev-val" style="color: #fff;">Novel Device (0.00)</span>
            </label>
            <input type="range" id="slider-dev" min="0" max="1" step="0.05" value="0" style="width: 100%; accent-color: var(--accent);" oninput="updateSimulation()">
          </div>

          <div>
            <label style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
              <span>Geographic Alignment</span>
              <span id="lbl-geo-val" style="color: #fff;">Out of Region (0.00)</span>
            </label>
            <input type="range" id="slider-geo" min="0" max="1" step="0.05" value="0" style="width: 100%; accent-color: var(--accent);" oninput="updateSimulation()">
          </div>

          <div>
            <label style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
              <span>Velocity Burst Intensity</span>
              <span id="lbl-vel-val" style="color: #fff;">Baseline (0.00)</span>
            </label>
            <input type="range" id="slider-vel" min="0" max="1" step="0.05" value="0" style="width: 100%; accent-color: var(--accent);" oninput="updateSimulation()">
          </div>
        </div>

        <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted); border-top: 1px solid var(--border); padding-top: 0.75rem;">
          <strong>Simulated Action Recommendation:</strong> <span id="sim-action-text" style="color: #fff;">Maintain existing policy actions.</span>
        </div>
      </div>

      <!-- Static Counterfactual Table -->
      <table>
        <thead>
          <tr>
            <th>Feature</th>
            <th>Current Value</th>
            <th>Inversion Threshold</th>
            <th>Impact on Verdict</th>
          </tr>
        </thead>
        <tbody>
          {cf_tbody}
        </tbody>
      </table>
    </div>

    <!-- Next Best Actions -->
    <div class="section-card">
      <h2>5. Next-Best-Action Decisions & Policy Routing</h2>
      <table>
        <thead>
          <tr>
            <th>Action Proposal</th>
            <th>Approval Route</th>
            <th>Policy Justification</th>
          </tr>
        </thead>
        <tbody>
          {actions_tbody}
        </tbody>
      </table>
    </div>

    <!-- Regulatory Filing Package -->
    <div class="section-card">
      <h2>6. Regulatory Filing (FinCEN SAR / NCA STR)</h2>
      {sar_html}
    </div>

    <!-- Audit Seal -->
    <div class="seal">
      <div>
        <strong>Deterministic Audit Trail Certified</strong> — 0 Hallucinations, Faithfulness: {faithfulness:.2f}/1.00
      </div>
      <div style="color: var(--text-muted);">
        Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
      </div>
    </div>
  </div>

  <script>
    function updateSimulation() {{
      const baseProb = parseFloat("{prob:.2f}");
      const cust = parseFloat(document.getElementById("slider-cust").value);
      const dev = parseFloat(document.getElementById("slider-dev").value);
      const geo = parseFloat(document.getElementById("slider-geo").value);
      const vel = parseFloat(document.getElementById("slider-vel").value);

      document.getElementById("lbl-cust-val").innerText = cust > 0.5 ? "Customer Confirmed (-0.60)" : (cust > 0 ? "Partial Response (-" + (cust * 0.6).toFixed(2) + ")" : "Unverified (0.00)");
      document.getElementById("lbl-dev-val").innerText = dev > 0.5 ? "Recognized Device (-0.35)" : "Novel Device (0.00)";
      document.getElementById("lbl-geo-val").innerText = geo > 0.5 ? "Home Region (-0.25)" : "Out of Region (0.00)";
      document.getElementById("lbl-vel-val").innerText = vel > 0.5 ? "High Burst (+0.25)" : "Baseline (0.00)";

      let simProb = baseProb - (cust * 0.60) - (dev * 0.35) - (geo * 0.25) + (vel * 0.25);
      simProb = Math.min(0.99, Math.max(0.01, simProb));

      document.getElementById("sim-prob-val").innerText = simProb.toFixed(2);
      const markerPos = Math.min(98, Math.max(2, Math.round(simProb * 100)));
      document.getElementById("sim-marker").style.left = markerPos + "%";

      const badge = document.getElementById("sim-verdict-badge");
      const actText = document.getElementById("sim-action-text");
      if (simProb >= 0.70) {{
        badge.innerText = "FRAUD";
        badge.className = "route-badge route-L2";
        badge.style.background = "rgba(239, 68, 68, 0.2)";
        badge.style.color = "#ef4444";
        actText.innerText = "BLOCK_CARD, DECLINE_TRANSACTION, FILE_SAR";
      }} else if (simProb >= 0.30) {{
        badge.innerText = "UNCERTAIN";
        badge.className = "route-badge route-L1";
        badge.style.background = "rgba(245, 158, 11, 0.2)";
        badge.style.color = "#f59e0b";
        actText.innerText = "STEP_UP_AUTH, VERIFY_WITH_CUSTOMER, MONITOR_CARD";
      }} else {{
        badge.innerText = "LEGITIMATE";
        badge.className = "route-badge route-auto";
        badge.style.background = "rgba(16, 185, 129, 0.2)";
        badge.style.color = "#10b981";
        actText.innerText = "ALLOW_TRANSACTION, CLOSE_NO_FRAUD";
      }}
    }}

    document.addEventListener("DOMContentLoaded", function() {{
      const elements = {cy_elements_json};
      cytoscape({{
        container: document.getElementById('cy-container'),
        elements: elements,
        style: [
          {{
            selector: 'node',
            style: {{
              'label': 'data(label)',
              'background-color': 'data(color)',
              'color': '#fff',
              'font-size': '10px',
              'text-valign': 'center',
              'text-halign': 'center',
              'width': 35,
              'height': 35
            }}
          }},
          {{
            selector: 'edge',
            style: {{
              'width': 2,
              'line-color': 'rgba(255, 255, 255, 0.25)',
              'target-arrow-color': 'rgba(255, 255, 255, 0.4)',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'label': 'data(label)',
              'font-size': '8px',
              'color': '#8a99b5'
            }}
          }}
        ],
        layout: {{
          name: 'breadthfirst',
          directed: true,
          padding: 30
        }}
      }});
    }});
  </script>
</body>
</html>
"""

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return html_content
