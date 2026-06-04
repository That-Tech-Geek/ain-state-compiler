document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = ""; // Local relative path
  let activeImm = "product_deployment_imm";

  // Elements
  const ingestStream = document.getElementById("ingest-stream");
  const ingestCount = document.getElementById("ingest-count");
  const conflictCount = document.getElementById("conflict-count");
  const conflictsContainer = document.getElementById("conflicts-container");
  const matricesContainer = document.getElementById("matrices-container");
  const immViewer = document.getElementById("imm-viewer");
  
  // Metrics Elements
  const metricJson = document.getElementById("metric-json");
  const metricYaml = document.getElementById("metric-yaml");
  const metricPercentage = document.getElementById("metric-percentage");
  const metricSavedTokens = document.getElementById("metric-saved-tokens");
  
  // Controls
  const btnCron = document.getElementById("btn-cron");
  const overlayLoader = document.getElementById("overlay-loader");
  const tabButtons = document.querySelectorAll(".tab-btn");

  // Format Timestamps cleanly
  function formatTime(isoString) {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " - " + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  // Fetch raw feed cards
  async function loadRawFeeds() {
    try {
      const res = await fetch(`${API_BASE}/api/raw-feeds`);
      const data = await res.json();
      
      let html = "";
      let count = 0;

      // Collect all feeds into a sorted timeline
      const timeline = [];
      data.slack.forEach(item => {
        timeline.push({ ...item, type: "slack" });
        count++;
      });
      data.jira.forEach(item => {
        timeline.push({ ...item, type: "jira", timestamp: item.updated_at });
        count++;
      });
      data.emails.forEach(item => {
        timeline.push({ ...item, type: "gmail" });
        count++;
      });

      // Sort timeline descending
      timeline.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      timeline.forEach(item => {
        if (item.type === "slack") {
          html += `
            <div class="stream-card">
              <div class="card-meta">
                <span class="source-badge slack">Slack #${item.channel}</span>
                <span class="card-time">${formatTime(item.timestamp)}</span>
              </div>
              <div class="card-author">@${item.user}</div>
              <div class="card-text">${item.text}</div>
            </div>
          `;
        } else if (item.type === "jira") {
          html += `
            <div class="stream-card">
              <div class="card-meta">
                <span class="source-badge jira">Jira Ticket</span>
                <span class="card-time">${formatTime(item.timestamp)}</span>
              </div>
              <div class="card-author">${item.id}: ${item.title}</div>
              <div class="card-text">Status: <strong>${item.status}</strong> | Assignee: @${item.assignee}</div>
            </div>
          `;
        } else if (item.type === "gmail") {
          html += `
            <div class="stream-card">
              <div class="card-meta">
                <span class="source-badge gmail">Gmail Inflow</span>
                <span class="card-time">${formatTime(item.timestamp)}</span>
              </div>
              <div class="card-author">From: ${item.from}</div>
              <div class="card-text"><strong>Subj: ${item.subject}</strong><br>${item.body}</div>
            </div>
          `;
        }
      });

      ingestStream.innerHTML = html;
      ingestCount.textContent = count;
    } catch (e) {
      console.error("Error loading raw feeds", e);
    }
  }

  // Load compiled state (conflicts + matrices)
  async function loadState() {
    try {
      const res = await fetch(`${API_BASE}/api/state`);
      const data = await res.json();
      
      // Populate Conflicts
      const conflicts = data.operational_execution_graph.conflict_disputes;
      conflictCount.textContent = `${conflicts.length} Contradictions`;
      
      if (conflicts.length === 0) {
        conflictsContainer.innerHTML = `<div class="panel-desc">🟢 No active contradiction anomalies detected.</div>`;
      } else {
        let conflictHtml = "";
        conflicts.forEach(c => {
          const sevClass = c.severity.toLowerCase() === "critical" ? "severity-critical" : "severity-high";
          conflictHtml += `
            <div class="conflict-card ${sevClass}">
              <div class="conflict-title">
                <span class="sev-badge">${c.severity}</span>
                ${c.title}
              </div>
              <div class="conflict-summary">${c.summary}</div>
              <div class="conflict-evidence">
                ${c.evidence.map(e => `<div class="evidence-item">⚠️ ${e}</div>`).join("")}
              </div>
              <div class="conflict-action">
                <strong>CTO Resolution Gate:</strong> ${c.resolution}
              </div>
            </div>
          `;
        });
        conflictsContainer.innerHTML = conflictHtml;
      }

      // Populate Matrices
      const nodes = data.operational_execution_graph.active_state_nodes;
      let matrixHtml = "";

      // Matrix 1: Analytics Release State
      const analyticState = nodes.analytics_v2;
      matrixHtml += `
        <div class="matrix-card">
          <div class="matrix-title">
            Product Deployment State: Analytics v2
            <span class="matrix-status discrepancy">PAUSED IN PRODUCTION</span>
          </div>
          <div class="matrix-grid">
            <div class="grid-cell">
              <span class="cell-label">Jira ENG-1043</span>
              <span class="cell-value">${analyticState.jira_status}</span>
            </div>
            <div class="grid-cell">
              <span class="cell-label">Marketing Claim</span>
              <span class="cell-value">${analyticState.marketing_claim}</span>
            </div>
            <div class="grid-cell">
              <span class="cell-label">Production Flag</span>
              <span class="cell-value highlight-red">${analyticState.production_flag}</span>
            </div>
          </div>
        </div>
      `;

      // Matrix 2: Acme Billing Exception
      const billingState = nodes.acme_corp_billing;
      matrixHtml += `
        <div class="matrix-card">
          <div class="matrix-title">
            Billing Account Exception: Acme Corp
            <span class="matrix-status discrepancy">DISCREPANCY WARNING</span>
          </div>
          <div class="matrix-grid">
            <div class="grid-cell">
              <span class="cell-label">Slack override</span>
              <span class="cell-value highlight-amber">${billingState.agreed_discount} Discount</span>
            </div>
            <div class="grid-cell">
              <span class="cell-label">Jira BI-402</span>
              <span class="cell-value">${billingState.pending_jira}</span>
            </div>
            <div class="grid-cell">
              <span class="cell-label">Active Invoice</span>
              <span class="cell-value highlight-red">${billingState.invoiced_amount}</span>
            </div>
          </div>
        </div>
      `;

      matricesContainer.innerHTML = matrixHtml;
    } catch (e) {
      console.error("Error loading compiled state", e);
    }
  }

  // Load IMM Viewer text
  async function loadImmViewer() {
    try {
      if (activeImm === "operational_state") {
        // Load raw YAML operational state
        const res = await fetch(`${API_BASE}/api/imm?name=operational_state`);
        const data = await res.json();
        immViewer.textContent = data.content;
      } else {
        // Load standard markdown IMMs
        const res = await fetch(`${API_BASE}/api/imm?name=${activeImm}`);
        const data = await res.json();
        immViewer.textContent = data.content;
      }
    } catch (e) {
      console.error("Error loading IMM", e);
      immViewer.textContent = "Error loading IMM module.";
    }
  }

  // Load Token Optimization metrics
  async function loadMetrics() {
    try {
      const res = await fetch(`${API_BASE}/api/metrics`);
      const data = await res.json();
      
      metricJson.textContent = data.json_characters.toLocaleString();
      metricYaml.textContent = data.yaml_characters.toLocaleString();
      metricPercentage.textContent = `${data.saving_percentage}%`;
      metricSavedTokens.textContent = data.saved_tokens.toLocaleString();
    } catch (e) {
      console.error("Error loading metrics", e);
    }
  }

  // Initialize
  async function loadAll() {
    await loadRawFeeds();
    await loadState();
    await loadImmViewer();
    await loadMetrics();
    
    // Update last sync time indicator
    const now = new Date();
    document.getElementById("last-sync-time").textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Tabs Handler
  tabButtons.forEach(btn => {
    btn.addEventListener("click", (e) => {
      tabButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeImm = btn.getAttribute("data-imm");
      loadImmViewer();
    });
  });

  // Off-Hours Cron Execution
  btnCron.addEventListener("click", async () => {
    // Show overlay loader with slight delay to show micro-animations
    overlayLoader.classList.remove("hidden");
    
    try {
      // Trigger compile (which triggers sync_hivemind + compiler.compile)
      const res = await fetch(`${API_BASE}/api/compile`);
      const data = await res.json();
      
      // Keep overlay for 1.2s to visual feedback
      setTimeout(() => {
        overlayLoader.classList.add("hidden");
        loadAll();
      }, 1200);
    } catch (e) {
      console.error("Cron failed", e);
      overlayLoader.classList.add("hidden");
    }
  });

  // Query Terminal Event Trigger
  const btnQuery = document.getElementById("btn-query");
  const queryInput = document.getElementById("query-input");
  const queryResponseBox = document.getElementById("query-response-box");
  const responseSource = document.getElementById("response-source");
  const responseLlm = document.getElementById("response-llm");
  const queryResponseText = document.getElementById("query-response-text");

  btnQuery.addEventListener("click", async () => {
    const queryText = queryInput.value.trim();
    if (!queryText) return;
    
    btnQuery.textContent = "QUERYING...";
    btnQuery.disabled = true;
    
    try {
      const res = await fetch(`${API_BASE}/api/query?text=${encodeURIComponent(queryText)}`);
      const data = await res.json();
      
      responseSource.textContent = data.node;
      responseLlm.textContent = data.is_llm ? "ACTIVE (Gemma)" : "OFFLINE (State Solver)";
      queryResponseText.textContent = data.answer;
      
      queryResponseBox.classList.remove("hidden");
    } catch (e) {
      console.error("Query failed", e);
      queryResponseText.textContent = "Error communicating with G-Brain on-demand query endpoint.";
      queryResponseBox.classList.remove("hidden");
    } finally {
      btnQuery.textContent = "QUERY";
      btnQuery.disabled = false;
    }
  });

  // Allow enter key in query box
  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      btnQuery.click();
    }
  });

  // Load initial view
  loadAll();
});
