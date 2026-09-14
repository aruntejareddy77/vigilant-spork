/**
 * app.js
 * Central single-page application controller for Sovereign AI Workbench.
 * Zero external CDN dependencies. Pure vanilla ES6.
 */

// Central Application State Store
const appState = {
  currentRole: 'engineer',
  activeTaskId: null,
  activeThreadId: null,
  activeDemoId: null,
  networkEvents: [],
  networkCounters: {
    total: 0,
    allowed: 0,
    denied: 0,
    leaks: 0
  },
  hitlAlerts: [],
  previewRenderer: null,
  sockets: {
    network: null,
    hitl: null,
    trace: null
  },
  pingIntervals: {}
};

// Initialize Application on DOMContentLoaded
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    initUI();
    initPreview();
    initWebSockets();
    bindRoleSelector();
    bindTaskForm();
    bindDemoButtons();
    bindEgressCheckButton();
    bindPreviewControls();
  });
}

function initUI() {
  switchRole(appState.currentRole);
}

function initPreview() {
  if (typeof DocumentPreviewRenderer !== 'undefined') {
    appState.previewRenderer = new DocumentPreviewRenderer('preview-canvas', 'preview-image');
  }
}

/**
 * Dynamic Role Switching and View Filtering (FR-UI-5 / UI-05).
 * Enforces least-privilege view constraints across Admin, Engineer, and Auditor.
 */
function switchRole(role) {
  appState.currentRole = role;

  if (typeof document === 'undefined') return;

  const roleSelect = document.getElementById('role-selector');
  if (roleSelect && roleSelect.value !== role) {
    roleSelect.value = role;
  }

  const taskFormContainer = document.getElementById('task-submission-container');
  const auditorNotice = document.getElementById('auditor-notice');
  const demoButtons = document.querySelectorAll('.btn-demo');
  const hitlActionButtons = document.querySelectorAll('.hitl-actions button');
  const hitlAuditorBadges = document.querySelectorAll('.hitl-auditor-badge');

  if (role === 'auditor') {
    // Hide task submission form
    if (taskFormContainer) taskFormContainer.style.display = 'none';
    // Display prominent auditor notice banner
    if (auditorNotice) auditorNotice.style.display = 'flex';
    // Disable demo launcher buttons
    demoButtons.forEach(btn => {
      btn.disabled = true;
      btn.title = 'Demo execution disabled in Auditor clearance mode per FR-UI-5';
    });
    // Disable HITL approval buttons
    hitlActionButtons.forEach(btn => {
      btn.style.display = 'none';
    });
    hitlAuditorBadges.forEach(badge => {
      badge.style.display = 'inline-block';
    });
  } else if (role === 'engineer' || role === 'admin') {
    // Show task submission form
    if (taskFormContainer) taskFormContainer.style.display = 'block';
    // Hide auditor notice
    if (auditorNotice) auditorNotice.style.display = 'none';
    // Enable demo launcher buttons
    demoButtons.forEach(btn => {
      btn.disabled = false;
      btn.removeAttribute('title');
    });
    // Enable HITL approval buttons
    hitlActionButtons.forEach(btn => {
      btn.style.display = 'inline-flex';
      btn.disabled = false;
    });
    hitlAuditorBadges.forEach(badge => {
      badge.style.display = 'none';
    });
  }
}

function bindRoleSelector() {
  const roleSelector = document.getElementById('role-selector');
  if (roleSelector) {
    roleSelector.addEventListener('change', (e) => {
      switchRole(e.target.value);
    });
  }
}

function bindTaskForm() {
  const submitBtn = document.getElementById('btn-submit-task');
  if (submitBtn) {
    submitBtn.addEventListener('click', handleTaskSubmit);
  }
}

function handleTaskSubmit() {
  if (appState.currentRole === 'auditor') {
    alert('Auditor Clearance Active: Task submission disabled per least-privilege policy (FR-UI-5).');
    return;
  }
  const promptInput = document.getElementById('task-prompt');
  const prompt = promptInput ? promptInput.value.trim() : '';
  if (!prompt) return;

  const submitBtn = document.getElementById('btn-submit-task');
  if (submitBtn) submitBtn.disabled = true;

  fetch('/api/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Sovereign-Role': appState.currentRole
    },
    body: JSON.stringify({ prompt: prompt })
  })
  .then(res => {
    if (submitBtn) submitBtn.disabled = false;
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then(data => {
    if (data.task_id) {
      appState.activeTaskId = data.task_id;
      appState.activeThreadId = data.thread_id;
      updateTaskBadge(data.task_id, 'RUNNING');
      connectTraceWebSocket(data.task_id);
      if (promptInput) promptInput.value = '';
    }
  })
  .catch(err => {
    if (submitBtn) submitBtn.disabled = false;
    console.error('Task submission failed:', err);
  });
}

function bindDemoButtons() {
  const buttons = [
    { id: 'btn-demo-a', demo: 'demo_a' },
    { id: 'btn-demo-b', demo: 'demo_b' },
    { id: 'btn-demo-c', demo: 'demo_c' }
  ];

  buttons.forEach(({ id, demo }) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', () => launchDemo(demo));
    }
  });
}

function bindPreviewControls() {
  const prevBtn = document.getElementById('btn-prev-page');
  const nextBtn = document.getElementById('btn-next-page');
  const zoomResetBtn = document.getElementById('btn-zoom-reset');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (appState.previewRenderer) appState.previewRenderer.prevPage();
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (appState.previewRenderer) appState.previewRenderer.nextPage();
    });
  }
  if (zoomResetBtn) {
    zoomResetBtn.addEventListener('click', () => {
      if (appState.previewRenderer) appState.previewRenderer.setZoom(1.0);
    });
  }
}

function launchDemo(demoId) {
  if (appState.currentRole === 'auditor') {
    alert('Auditor Clearance Active: Demo execution disabled per least-privilege policy (FR-UI-5).');
    return;
  }

  appState.activeDemoId = demoId;
  initDemoStepIndicator(demoId);

  fetch(`/api/demos/${demoId}/launch`, {
    method: 'POST',
    headers: {
      'X-Sovereign-Role': appState.currentRole
    }
  })
  .then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then(data => {
    if (data.task_id) {
      appState.activeTaskId = data.task_id;
      appState.activeThreadId = data.thread_id;
      updateTaskBadge(data.task_id, data.status || 'RUNNING');
      connectTraceWebSocket(data.task_id);

      // Handle demo-specific preview loading
      handleDemoPreviewData(demoId, data);
    }
  })
  .catch(err => console.error(`Failed to launch ${demoId}:`, err));
}

function initDemoStepIndicator(demoId) {
  const container = document.getElementById('demo-step-container');
  const title = document.getElementById('active-demo-title');
  const list = document.getElementById('demo-step-list');
  if (!container || !title || !list) return;

  const demoConfigs = {
    demo_a: {
      title: 'Demo A: Inspection Report Workflow',
      steps: [
        '1. Ingest Inspection Report',
        '2. OCR & Findings Extraction',
        '3. Human-in-the-Loop Sign-Off',
        '4. Export Verified Memo (.docx)'
      ]
    },
    demo_b: {
      title: 'Demo B: Code Gen & Sandbox',
      steps: [
        '1. Ingest Historian CSV Data',
        '2. Generate Vibration Analysis Code',
        '3. Execute Isolated CodeSandbox',
        '4. Bounded Auto-Fix Retry Loop',
        '5. Deliver Verified Script & Logs'
      ]
    },
    demo_c: {
      title: 'Demo C: P&ID Drawing Revision Diff',
      steps: [
        '1. Align Revision A & Revision B',
        '2. Multi-Layer Diff Detection',
        '3. Render Color-Coded Overlay',
        '4. Export Revision Change Table'
      ]
    }
  };

  const config = demoConfigs[demoId] || { title: 'Workflow Steps', steps: [] };
  title.textContent = config.title;
  list.innerHTML = '';

  config.steps.forEach((stepText, idx) => {
    const li = document.createElement('li');
    li.className = `step-item ${idx === 0 ? 'active' : ''}`;
    li.id = `demo-step-${idx + 1}`;
    li.innerHTML = `<span>${stepText}</span> <span class="step-badge">${idx === 0 ? 'RUNNING' : 'PENDING'}</span>`;
    list.appendChild(li);
  });

  container.style.display = 'block';
}

function updateDemoStepStatus(stepNumber, status) {
  const stepEl = document.getElementById(`demo-step-${stepNumber}`);
  if (!stepEl) return;

  stepEl.className = `step-item ${status.toLowerCase()}`;
  const badge = stepEl.querySelector('.step-badge');
  if (badge) {
    badge.textContent = status.toUpperCase();
  }
}

function handleDemoPreviewData(demoId, data) {
  if (!appState.previewRenderer) return;

  if (demoId === 'demo_a') {
    // Mock sample inspection report with bounding boxes
    const docData = {
      doc_id: 'doc-v301',
      total_pages: 1,
      pages: [
        {
          page_number: 1,
          width: 2480,
          height: 3508,
          regions: [
            { region_id: 'p1-r001', box_2d: [0.08, 0.1, 0.14, 0.9], text: 'REFINERY VESSEL V-301 INSPECTION REPORT', confidence: 0.98, modality: 'printed' },
            { region_id: 'p1-r002', box_2d: [0.18, 0.1, 0.23, 0.5], text: 'Operating Pressure: 42.5 bar', confidence: 0.94, modality: 'printed' },
            { region_id: 'p1-r003', box_2d: [0.25, 0.1, 0.30, 0.85], text: 'Shell Wall Thickness Minimum: 3.2 mm (Required: 3.0 mm)', confidence: 0.96, modality: 'printed' },
            { region_id: 'p1-r004', box_2d: [0.35, 0.1, 0.42, 0.8], text: 'Localized pitting observed at nozzle N-2 weld zone', confidence: 0.78, modality: 'handwritten' } // <0.85 triggers review amber
          ]
        }
      ]
    };
    appState.previewRenderer.setDocument(docData);
  } else if (demoId === 'demo_c') {
    // Mock P&ID Drawing Revision Comparison with visual diff overlay
    const diffData = {
      doc_id: 'pid-vessel-rev-b',
      total_pages: 1,
      pages: [
        {
          page_number: 1,
          width: 3300,
          height: 2550,
          regions: [
            { region_id: 'diff-add-01', box_2d: [0.3, 0.25, 0.42, 0.42], text: 'Added bypass relief valve RV-402', diff_status: 'added' },
            { region_id: 'diff-mod-01', box_2d: [0.5, 0.6, 0.65, 0.78], text: 'Pipe diameter upsized 3" -> 4"', diff_status: 'modified' },
            { region_id: 'diff-rem-01', box_2d: [0.7, 0.15, 0.82, 0.32], text: 'Decommissioned manual sampling cock SC-101', diff_status: 'removed' }
          ]
        }
      ]
    };
    appState.previewRenderer.setDocument(diffData);
  }
}

function bindEgressCheckButton() {
  const btn = document.getElementById('btn-run-egress-check');
  if (btn) {
    btn.addEventListener('click', () => {
      btn.disabled = true;
      btn.innerHTML = '<svg class="btn-icon"><use href="#icon-refresh"/></svg> Probing Network...';
      fetch('/api/network/test-egress', {
        method: 'POST',
        headers: {
          'X-Sovereign-Role': appState.currentRole
        }
      })
      .then(res => res.json())
      .then(results => {
        btn.disabled = false;
        btn.innerHTML = '<svg class="btn-icon"><use href="#icon-refresh"/></svg> Run Egress Check';
        // Add synthetic egress results to network monitor
        if (results && results.probes) {
          for (const probe of results.probes) {
            renderNetworkEvent({
              timestamp_iso: new Date().toISOString(),
              protocol: probe.protocol || 'TCP',
              process_name: 'sovereign-egress-probe',
              pid: 9999,
              local_address: '127.0.0.1:0',
              remote_address: `${probe.target_host}:${probe.target_port}`,
              verdict: probe.blocked ? 'DENY' : 'ALLOW',
              reason: probe.details || (probe.blocked ? 'Blocked by air-gap policy' : 'Egress allowed')
            });
          }
        }
      })
      .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '<svg class="btn-icon"><use href="#icon-refresh"/></svg> Run Egress Check';
        console.error('Egress test failed:', err);
      });
    });
  }
}

function updateTaskBadge(taskId, status) {
  const badge = document.getElementById('trace-task-badge');
  if (badge) {
    badge.textContent = `${taskId} [${status}]`;
    if (status === 'RUNNING') {
      badge.className = 'badge badge-airgap';
    } else if (status === 'COMPLETED') {
      badge.className = 'badge badge-egress';
    } else {
      badge.className = 'badge badge-secondary';
    }
  }
}

// ── WebSocket Streaming Management ──────────────────────────────────────────

function initWebSockets() {
  connectNetworkWebSocket();
  connectHITLWebSocket();
}

function getWebSocketUrl(path) {
  if (typeof window === 'undefined') return '';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host || 'localhost:8000';
  return `${protocol}//${host}${path}`;
}

function connectNetworkWebSocket() {
  const wsUrl = getWebSocketUrl('/ws/network');
  try {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      // Ping keepalive every 20 seconds
      clearInterval(appState.pingIntervals.network);
      appState.pingIntervals.network = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 20000);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'NETWORK_EVENT' || data.type === 'EGRESS_ALERT') {
          renderNetworkEvent(data.event);
        }
      } catch (e) {}
    };
    ws.onclose = () => {
      clearInterval(appState.pingIntervals.network);
      // Auto-reconnect after 3 seconds
      setTimeout(connectNetworkWebSocket, 3000);
    };
    appState.sockets.network = ws;
  } catch (e) {}
}

function connectHITLWebSocket() {
  const wsUrl = getWebSocketUrl('/ws/hitl');
  try {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      clearInterval(appState.pingIntervals.hitl);
      appState.pingIntervals.hitl = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 20000);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'HITL_SUSPENDED' || data.type === 'HITL_ALERT') {
          renderHITLCard(data);
        }
      } catch (e) {}
    };
    ws.onclose = () => {
      clearInterval(appState.pingIntervals.hitl);
      setTimeout(connectHITLWebSocket, 3000);
    };
    appState.sockets.hitl = ws;
  } catch (e) {}
}

function connectTraceWebSocket(taskId) {
  if (appState.sockets.trace) {
    try { appState.sockets.trace.close(); } catch (e) {}
  }
  clearInterval(appState.pingIntervals.trace);

  const wsUrl = getWebSocketUrl(`/ws/tasks/${taskId}`);
  try {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      appState.pingIntervals.trace = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 15000);
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'TRACE_STEP') {
          renderTraceStep(data);
        } else if (data.type === 'HITL_SUSPENDED') {
          renderHITLCard(data);
          updateTaskBadge(taskId, 'SUSPENDED');
        } else if (data.type === 'TASK_COMPLETED') {
          updateTaskBadge(taskId, 'COMPLETED');
        }
      } catch (e) {}
    };
    appState.sockets.trace = ws;
  } catch (e) {}
}

// ── Rendering Functions ─────────────────────────────────────────────────────

function renderTraceStep(step) {
  const timeline = document.getElementById('trace-timeline');
  if (!timeline) return;

  const emptyState = timeline.querySelector('.timeline-empty-state');
  if (emptyState) emptyState.remove();

  const card = document.createElement('div');
  card.className = 'trace-step-card';

  const header = document.createElement('div');
  header.className = 'step-header';
  const nodeName = document.createElement('span');
  nodeName.className = 'step-node-name';
  nodeName.textContent = step.node_name || `Step ${step.step_index || 1}`;

  const meta = document.createElement('div');
  meta.className = 'step-meta';
  if (step.elapsed_ms !== undefined && step.elapsed_ms !== null) {
    const elapsed = document.createElement('span');
    elapsed.textContent = `${Number(step.elapsed_ms).toFixed(1)}ms`;
    meta.appendChild(elapsed);
  }
  if (step.model_id) {
    const model = document.createElement('span');
    model.className = 'badge badge-secondary';
    model.textContent = step.model_id;
    meta.appendChild(model);
  }

  header.appendChild(nodeName);
  header.appendChild(meta);
  card.appendChild(header);

  const body = document.createElement('div');
  body.className = 'step-body';

  if (step.thought) {
    const thought = document.createElement('p');
    thought.className = 'step-thought';
    thought.textContent = step.thought;
    body.appendChild(thought);
  }

  if (step.tool_calls && step.tool_calls.length > 0) {
    for (const tool of step.tool_calls) {
      const toolEl = document.createElement('div');
      toolEl.className = 'step-tool';
      const toolName = tool.tool || tool.name || 'tool';
      const toolInputs = JSON.stringify(tool.inputs || tool.args || {});
      toolEl.textContent = `Invoke: ${toolName}(${toolInputs})`;
      body.appendChild(toolEl);
    }
  }

  if (step.artifact_url || step.download_url) {
    const link = document.createElement('a');
    link.className = 'step-artifact-link';
    link.href = step.artifact_url || step.download_url;
    link.download = step.artifact_name || 'deliverable';
    link.innerHTML = `<svg class="btn-icon"><use href="#icon-document"/></svg> Download Deliverable: ${step.artifact_name || 'Output'}`;
    body.appendChild(link);
  }

  card.appendChild(body);
  timeline.appendChild(card);
  timeline.scrollTop = timeline.scrollHeight;
}

function renderHITLCard(alertData) {
  const container = document.getElementById('hitl-queue-container');
  if (!container) return;

  const emptyState = container.querySelector('.hitl-empty-state');
  if (emptyState) emptyState.remove();

  // Avoid duplicate cards for same task
  const existingCard = document.getElementById(`hitl-${alertData.task_id}`);
  if (existingCard) existingCard.remove();

  const card = document.createElement('div');
  card.className = 'hitl-card';
  card.id = `hitl-${alertData.task_id}`;

  const cardHeader = document.createElement('div');
  cardHeader.className = 'hitl-card-header';
  const title = document.createElement('span');
  title.className = 'hitl-title';
  title.textContent = 'Pending Deliverable Sign-Off';
  const badge = document.createElement('span');
  badge.className = 'badge badge-secondary';
  badge.textContent = alertData.pending_approval?.action || 'Review';
  cardHeader.appendChild(title);
  cardHeader.appendChild(badge);
  card.appendChild(cardHeader);

  const summary = document.createElement('p');
  summary.className = 'hitl-summary';
  summary.textContent = alertData.pending_approval?.summary || 'Operator review required before proceeding.';
  card.appendChild(summary);

  // Source citations
  const citationsContainer = document.createElement('div');
  citationsContainer.className = 'hitl-citations';
  const citations = alertData.pending_approval?.citations || [];
  for (const cit of citations) {
    const pill = document.createElement('span');
    pill.className = 'citation-pill';
    pill.textContent = cit;
    pill.title = 'Click to highlight region on preview canvas';
    pill.onclick = () => {
      if (appState.previewRenderer) {
        const regionId = cit.includes('#') ? cit.split('#')[1] : cit;
        appState.previewRenderer.selectRegion(regionId);
      }
    };
    citationsContainer.appendChild(pill);
  }
  card.appendChild(citationsContainer);

  const notesInput = document.createElement('textarea');
  notesInput.className = 'hitl-notes-input';
  notesInput.placeholder = 'Operator sign-off notes or review comments...';
  notesInput.rows = 2;
  card.appendChild(notesInput);

  const actions = document.createElement('div');
  actions.className = 'hitl-actions';

  const isAuditor = appState.currentRole === 'auditor';

  const auditorBadge = document.createElement('span');
  auditorBadge.className = 'hitl-auditor-badge';
  auditorBadge.textContent = 'Auditor Clearance: Approval actions restricted to Lead Engineers';
  auditorBadge.style.display = isAuditor ? 'inline-block' : 'none';
  actions.appendChild(auditorBadge);

  const rejectBtn = document.createElement('button');
  rejectBtn.className = 'btn btn-sm btn-reject';
  rejectBtn.textContent = 'Reject';
  rejectBtn.style.display = isAuditor ? 'none' : 'inline-flex';
  rejectBtn.onclick = () => resumeTask(alertData.task_id, 'reject', notesInput.value);

  const approveBtn = document.createElement('button');
  approveBtn.className = 'btn btn-sm btn-approve';
  approveBtn.textContent = 'Approve Deliverable';
  approveBtn.style.display = isAuditor ? 'none' : 'inline-flex';
  approveBtn.onclick = () => resumeTask(alertData.task_id, 'approve', notesInput.value);

  actions.appendChild(rejectBtn);
  actions.appendChild(approveBtn);
  card.appendChild(actions);

  container.appendChild(card);
  updateHITLCountBadge();
}

function updateHITLCountBadge() {
  const container = document.getElementById('hitl-queue-container');
  const countBadge = document.getElementById('hitl-count-badge');
  if (!container || !countBadge) return;
  const cards = container.querySelectorAll('.hitl-card');
  countBadge.textContent = `${cards.length} Pending`;
  countBadge.className = cards.length > 0 ? 'badge badge-egress' : 'badge badge-secondary';
}

function resumeTask(taskId, decision, notes) {
  if (appState.currentRole === 'auditor') {
    alert('Auditor Clearance: Task resumption restricted per least-privilege policy.');
    return;
  }

  fetch(`/api/tasks/${taskId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Sovereign-Role': appState.currentRole
    },
    body: JSON.stringify({ decision, notes })
  })
  .then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then(() => {
    const card = document.getElementById(`hitl-${taskId}`);
    if (card) card.remove();
    updateHITLCountBadge();

    // If active demo, advance step
    if (appState.activeDemoId === 'demo_a') {
      updateDemoStepStatus(3, 'complete');
      updateDemoStepStatus(4, 'running');
    }
  })
  .catch(err => console.error('Resume failed:', err));
}

function renderNetworkEvent(event) {
  const tbody = document.getElementById('network-events-body');
  if (!tbody || !event) return;

  const emptyRow = tbody.querySelector('.table-empty-row');
  if (emptyRow) emptyRow.remove();

  appState.networkCounters.total += 1;
  if (event.verdict === 'ALLOW') {
    appState.networkCounters.allowed += 1;
  } else {
    appState.networkCounters.denied += 1;
  }

  const totalEl = document.getElementById('counter-total');
  const allowedEl = document.getElementById('counter-allowed');
  const deniedEl = document.getElementById('counter-denied');
  if (totalEl) totalEl.textContent = appState.networkCounters.total;
  if (allowedEl) allowedEl.textContent = appState.networkCounters.allowed;
  if (deniedEl) deniedEl.textContent = appState.networkCounters.denied;

  const tr = document.createElement('tr');
  const timestamp = event.timestamp_iso ? event.timestamp_iso.split('T')[1].split('.')[0] : '--:--:--';
  const proto = (event.protocol || 'TCP').toUpperCase();
  const processName = `${event.process_name || 'unknown'} (${event.pid || '?'})`;
  const localAddr = event.local_address || '127.0.0.1';
  const remoteAddr = event.remote_address || '127.0.0.1';
  const isAllow = event.verdict === 'ALLOW';

  tr.innerHTML = `
    <td>${timestamp}</td>
    <td>${proto}</td>
    <td>${processName}</td>
    <td>${localAddr}</td>
    <td>${remoteAddr}</td>
    <td><span class="badge-verdict ${isAllow ? 'badge-allow' : 'badge-deny'}">${event.verdict}</span></td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);

  while (tbody.children.length > 50) {
    tbody.removeChild(tbody.lastChild);
  }
}

// Module exports for unit testing environments
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    appState,
    switchRole,
    renderTraceStep,
    renderHITLCard,
    renderNetworkEvent,
    resumeTask,
    handleDemoPreviewData,
    initDemoStepIndicator
  };
}
