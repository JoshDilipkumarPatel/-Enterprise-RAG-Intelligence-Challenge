/* =====================================================
   Enterprise RAG Intelligence — Client Application
   ===================================================== */

(function () {
  "use strict";

  // --- DOM refs ------------------------------------------------------
  const userGrid = document.getElementById("user-grid");
  const queryInput = document.getElementById("query-input");
  const queryBtn = document.getElementById("query-btn");
  const btnText = queryBtn.querySelector(".btn-text");
  const btnSpinner = queryBtn.querySelector(".btn-spinner");
  const suggestionsEl = document.getElementById("query-suggestions");

  const answerCard = document.getElementById("answer-card");
  const skeletonCard = document.getElementById("skeleton-card");
  const strategyBadge = document.getElementById("strategy-badge");
  const confidenceFill = document.getElementById("confidence-fill");
  const confidenceValue = document.getElementById("confidence-value");
  const answerBody = document.getElementById("answer-body");
  const citationsList = document.getElementById("citations-list");
  const traceBody = document.getElementById("trace-body");

  // --- State ---------------------------------------------------------
  let selectedUser = null;
  let users = {};

  const ROLE_AVATARS = {
    "Finance Analyst": { cls: "avatar--finance", letter: "F" },
    "Budget Reviewer": { cls: "avatar--finance", letter: "F" },
    "Security Analyst": { cls: "avatar--security", letter: "S" },
    "HR Manager": { cls: "avatar--hr", letter: "H" },
    "Operations Manager": { cls: "avatar--operations", letter: "O" },
    "Executive": { cls: "avatar--executive", letter: "E" },
    "Compliance Officer": { cls: "avatar--compliance", letter: "C" },
    "Legal Counsel": { cls: "avatar--legal", letter: "L" },
  };

  const SUGGESTIONS = {
    "Finance Analyst": [
      "What changed in the vendor payment approval workflow?",
      "Show Q2 revenue and expense breakdown",
      "Which vendor invoices are blocked?",
    ],
    "Security Analyst": [
      "Show security alerts for impossible travel",
      "What did the penetration test find?",
      "List compliance audit control failures",
    ],
    "HR Manager": [
      "What are the employee benefits for 2026?",
      "What are the payroll audit findings?",
      "Show the employee directory",
    ],
    "Operations Manager": [
      "What is the cloud migration status?",
      "Show system health alerts",
      "List IT asset inventory",
    ],
    "Executive": [
      "Show the GDPR compliance assessment status",
      "What are the active vendor contracts and SLAs?",
      "Summarize the penetration test critical findings",
    ],
    "Compliance Officer": [
      "What is the GDPR compliance assessment status?",
      "Show compliance audit control failures",
      "What access audit events occurred this week?",
    ],
    "Legal Counsel": [
      "Summarize active vendor contracts and SLAs",
      "What is the GDPR remediation timeline?",
      "Which contracts are due for renewal?",
    ],
  };

  const SOURCE_ICONS = {
    document: "📄",
    csv: "📊",
    json_log: "📋",
    policy: "🔒",
  };

  // --- Init ----------------------------------------------------------
  async function init() {
    try {
      const res = await fetch("/api/users");
      users = await res.json();
      renderUsers();
    } catch (e) {
      userGrid.innerHTML =
        '<p style="color:var(--accent-red)">Failed to load users. Is the server running?</p>';
    }
  }

  // --- Render users --------------------------------------------------
  function renderUsers() {
    userGrid.innerHTML = "";
    for (const [uid, u] of Object.entries(users)) {
      const role = u.roles[0] || "";
      const av = ROLE_AVATARS[role] || { cls: "avatar--finance", letter: "?" };

      const tile = document.createElement("div");
      tile.className = "user-tile";
      tile.dataset.uid = uid;
      tile.innerHTML = `
        <div class="user-tile__avatar ${av.cls}">${av.letter}</div>
        <span class="user-tile__name">${u.display_name}</span>
        <span class="user-tile__role">${u.roles.join(", ")}</span>
      `;
      tile.addEventListener("click", () => selectUser(uid));
      userGrid.appendChild(tile);
    }
  }

  // --- Select user ---------------------------------------------------
  function selectUser(uid) {
    selectedUser = uid;
    document.querySelectorAll(".user-tile").forEach((t) =>
      t.classList.toggle("active", t.dataset.uid === uid)
    );
    queryBtn.disabled = !queryInput.value.trim();
    renderSuggestions();
  }

  // --- Suggestions ---------------------------------------------------
  function renderSuggestions() {
    suggestionsEl.innerHTML = "";
    if (!selectedUser) return;
    const role = users[selectedUser]?.roles[0] || "";
    const items = SUGGESTIONS[role] || [];
    items.forEach((text) => {
      const chip = document.createElement("span");
      chip.className = "suggestion-chip";
      chip.textContent = text;
      chip.addEventListener("click", () => {
        queryInput.value = text;
        queryBtn.disabled = false;
        submitQuery();
      });
      suggestionsEl.appendChild(chip);
    });
  }

  // --- Submit --------------------------------------------------------
  async function submitQuery() {
    const query = queryInput.value.trim();
    if (!selectedUser || !query) return;

    setLoading(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: selectedUser, query }),
      });
      const data = await res.json();
      if (data.error) {
        renderError(data.error);
      } else {
        renderAnswer(data);
      }
    } catch (e) {
      renderError("Network error — is the server running?");
    } finally {
      setLoading(false);
    }
  }

  // --- Loading state -------------------------------------------------
  function setLoading(on) {
    if (on) {
      answerCard.classList.add("hidden");
      skeletonCard.classList.remove("hidden");
      queryBtn.disabled = true;
      btnText.classList.add("hidden");
      btnSpinner.classList.remove("hidden");
    } else {
      skeletonCard.classList.add("hidden");
      queryBtn.disabled = false;
      btnText.classList.remove("hidden");
      btnSpinner.classList.add("hidden");
    }
  }

  // --- Render answer -------------------------------------------------
  function renderAnswer(data) {
    answerCard.classList.remove("hidden");

    // Strategy badge
    const strat = data.answer_strategy || "single_source";
    const labels = {
      multi_source: "Multi-Source",
      single_source: "Single Source",
      no_evidence: "No Evidence",
    };
    strategyBadge.textContent = labels[strat] || strat;
    strategyBadge.className = "strategy-badge strategy-badge--" + strat.replace("_", "-");

    // Confidence
    const conf = data.confidence ?? 0;
    confidenceFill.style.width = "0%";
    requestAnimationFrame(() => {
      confidenceFill.style.width = Math.round(conf * 100) + "%";
    });
    confidenceValue.textContent = (conf * 100).toFixed(0) + "%";

    // colour the bar by confidence level
    if (conf >= 0.7) {
      confidenceFill.style.background =
        "linear-gradient(90deg, var(--accent-green), var(--accent-cyan))";
    } else if (conf >= 0.4) {
      confidenceFill.style.background =
        "linear-gradient(90deg, var(--accent-blue), var(--accent-purple))";
    } else {
      confidenceFill.style.background =
        "linear-gradient(90deg, var(--accent-amber), var(--accent-red))";
    }

    // Answer body
    answerBody.textContent = data.answer;

    // Citations
    citationsList.innerHTML = "";
    (data.citations || []).forEach((c) => {
      const sourceMatch = c.match(/\(([^)]+)\)/);
      const sourcePath = sourceMatch ? sourceMatch[1] : "";
      const sourceType = guessSourceType(sourcePath);
      const icon = SOURCE_ICONS[sourceType] || "📎";

      const card = document.createElement("div");
      card.className = "citation-card";
      card.innerHTML = `<span class="citation-icon">${icon}</span><span class="citation-text">${escapeHtml(c)}</span>`;
      citationsList.appendChild(card);
    });

    // Trace
    renderTrace(data.trace);
  }

  function guessSourceType(path) {
    if (path.includes("documents/")) return "document";
    if (path.includes("structured/")) return "csv";
    if (path.includes("logs/")) return "json_log";
    if (path.includes("metadata/")) return "policy";
    return "document";
  }

  // --- Trace ---------------------------------------------------------
  function renderTrace(trace) {
    if (!trace) {
      traceBody.innerHTML = "<em>No trace data.</em>";
      return;
    }

    let html = "";

    if (trace.intent) {
      html += traceRow("intent_classification", trace.intent);
    }

    html += traceRow("routed_sources", (trace.routed_sources || []).join(", "));
    html += traceRow("route_reason", trace.route_reason || "—");
    html += traceRow("accessible_documents", trace.accessible_documents ?? "—");

    const blocked = trace.blocked_documents || [];
    html += traceRow(
      "blocked_documents",
      blocked.length === 0
        ? "0"
        : `<span class="trace-blocked">${blocked.length} blocked</span>`
    );

    blocked.forEach((bd) => {
      html += traceRow(
        "",
        `<span class="trace-blocked">✖ ${escapeHtml(bd.title)} — ${bd.reason} (needs ${bd.required_roles.join(", ")})</span>`
      );
    });

    if (trace.sensitivity_filter_applied) {
      html += traceRow(
        "sensitivity_filter",
        '<span class="trace-sensitivity">⚠ Sensitivity-level restriction applied</span>'
      );
    }

    if (trace.reranker_applied) {
      html += traceRow("reranker", "Applied (+position/coverage/diversity)");
    }

    if (trace.timings_ms) {
      for (const [name, value] of Object.entries(trace.timings_ms)) {
        html += traceRow(`timing_${name}`, `${value} ms`);
      }
    }

    (trace.retrieval_notes || []).forEach((note) => {
      html += traceRow("retrieval", note);
    });

    traceBody.innerHTML = html;
  }

  function traceRow(key, value) {
    return `<div class="trace-row"><span class="trace-key">${escapeHtml(key)}</span><span class="trace-value">${value}</span></div>`;
  }

  // --- Error ---------------------------------------------------------
  function renderError(msg) {
    answerCard.classList.remove("hidden");
    strategyBadge.textContent = "Error";
    strategyBadge.className = "strategy-badge strategy-badge--no-evidence";
    confidenceFill.style.width = "0%";
    confidenceValue.textContent = "—";
    answerBody.textContent = msg;
    citationsList.innerHTML = "";
    traceBody.innerHTML = "";
  }

  // --- Helpers -------------------------------------------------------
  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // --- Events --------------------------------------------------------
  queryInput.addEventListener("input", () => {
    queryBtn.disabled = !selectedUser || !queryInput.value.trim();
  });

  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitQuery();
    }
  });

  queryBtn.addEventListener("click", submitQuery);

  // --- Boot ----------------------------------------------------------
  init();
})();
