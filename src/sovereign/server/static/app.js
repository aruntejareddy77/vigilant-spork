/**
 * app.js
 * Central single-page application controller for Sovereign AI Workbench.
 * Zero external CDN dependencies. Pure vanilla ES6.
 */

// Global Application State
const appState = {
  currentRole: 'engineer',
  activeTaskId: null,
  activeThreadId: null,
  networkEvents: [],
  networkCounters: {
    total: 0,
    allowed: 0,
    denied: 0,
    leaks: 0
  },
  hitlQueue: [],
  previewRenderer: null,
  sockets: {
    network: null,
    hitl: null,
    trace: null
  }
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  initUI();
  initPreview();
  initWebSockets();
  bindRoleSelector();
  bindTaskForm();
  bindDemoButtons();
  bindEgressCheckButton();
});

function initUI() {
  switchRole(appState.currentRole);
}

function initPreview() {
  if (typeof DocumentPreviewRenderer !== 'undefined') {
    appState.previewRenderer = new DocumentPreviewRenderer('preview-canvas', 'preview-image');
  }
}

function switchRole(role) {
  appState.currentRole = role;
  const roleSelect = document.getElementById('role-selector');
  if (roleSelect && roleSelect.value !== role) {
    roleSelect.value = role;
  }

  const taskFormContainer = document.getElementById('task-submission-container');
  const auditorNotice = document.getElementById('auditor-notice');
  const demoButtons = document.querySelectorAll('.btn-demo');
  const hitlActionButtons = document.querySelectorAll('.hitl-actions button');

  if (role === 'auditor') {
    if (taskFormContainer) taskFormContainer.style.display = 'none';
    if (auditorNotice) auditorNotice.style.display = 'flex';
    demoButtons.forEach(btn => {
      btn.disabled = true;
      btn.title = 'Demo execution disabled in Auditor clearance mode';
    });
    hitlActionButtons.forEach(btn => {
      btn.disabled = true;
    });
  } else if (role === 'engineer' || role === 'admin') {
    if (taskFormContainer) taskFormContainer.style.display = 'block';
    if (auditorNotice) auditorNotice.style.display = 'none';
    demoButtons.forEach(btn => {
      btn.disabled = false;
      btn.removeAttribute('title');
    });
    hitlActionButtons.forEach(btn => {
      btn.disabled = false;
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

  fetch('/api/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Sovereign-Role': appState.currentRole
    },
    body: JSON.stringify({ prompt: prompt })
  })
  .then(res => res.json())
  .then(data => {
    if (data.task_id) {
      appState.activeTaskId = data.task_id;
      connectTraceWebSocket(data.task_id);
    }
  })
  .catch(err => console.error('Task submission failed:', err));
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

function launchDemo(demoId) {
  if (appState.currentRole === 'auditor') {
    alert('Auditor Clearance Active: Demo execution disabled per least-privilege policy (FR-UI-5).');
    return;
  }

  fetch(`/api/demos/${demoId}/launch`, {
    method: 'POST',
    headers: {
      'X-Sovereign-Role': appState.currentRole
    }
  })
  .then(res => res.json())
  .then(data => {
    if (data.task_id) {
      appState.activeTaskId = data.task_id;
      connectTraceWebSocket(data.task_id);
    }
  })
  .catch(err => console.error(`Failed to launch ${demoId}:`, err));
}

function bindEgressCheckButton() {
  const btn = document.getElementById('btn-run-egress-check');
  if (btn) {
    btn.addEventListener('click', () => {
      btn.disabled = true;
      btn.textContent = 'Running Probe...';
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
      })
      .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '<svg class="btn-icon"><use href="#icon-refresh"/></svg> Run Egress Check';
      });
    });
  }
}

function initWebSockets() {
  connectNetworkWebSocket();
  connectHITLWebSocket();
}

function connectNetworkWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/network`;
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'NETWORK_EVENT' || data.type === 'EGRESS_ALERT') {
          renderNetworkEvent(data.event);
        }
      } catch (e) {}
    };
    appState.sockets.network = ws;
  } catch (e) {}
}

function connectHITLWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/hitl`;
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'HITL_SUSPENDED' || data.type === 'HITL_ALERT') {
          renderHITLCard(data);
        }
      } catch (e) {}
    };
    appState.sockets.hitl = ws;
  } catch (e) {}
}

function connectTraceWebSocket(taskId) {
  if (appState.sockets.trace) {
    appState.sockets.trace.close();
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/tasks/${taskId}`;
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'TRACE_STEP') {
          renderTraceStep(data);
        } else if (data.type === 'HITL_SUSPENDED') {
          renderHITLCard(data);
        }
      } catch (e) {}
    };
    appState.sockets.trace = ws;
  } catch (e) {}
}

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
  if (step.elapsed_ms) {
    const elapsed = document.createElement('span');
    elapsed.textContent = `${step.elapsed_ms.toFixed(1)}ms`;
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
      toolEl.textContent = `Invoke: ${tool.tool || tool.name} (${JSON.stringify(tool.inputs || tool.args || {})})`;
      body.appendChild(toolEl);
    }
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

  const citationsContainer = document.createElement('div');
  citationsContainer.className = 'hitl-citations';
  const citations = alertData.pending_approval?.citations || [];
  for (const cit of citations) {
    const pill = document.createElement('span');
    pill.className = 'citation-pill';
    pill.textContent = cit;
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

  if (appState.currentRole === 'auditor') {
    const auditorBadge = document.createElement('span');
    auditorBadge.className = 'hitl-auditor-badge';
    auditorBadge.textContent = 'Auditor Clearance: Approval actions restricted to Lead Engineers';
    actions.appendChild(auditorBadge);
  } else {
    const rejectBtn = document.createElement('button');
    rejectBtn.className = 'btn btn-sm btn-reject';
    rejectBtn.textContent = 'Reject';
    rejectBtn.onclick = () => resumeTask(alertData.task_id, 'reject', notesInput.value);

    const approveBtn = document.createElement('button');
    approveBtn.className = 'btn btn-sm btn-approve';
    approveBtn.textContent = 'Approve Deliverable';
    approveBtn.onclick = () => resumeTask(alertData.task_id, 'approve', notesInput.value);

    actions.appendChild(rejectBtn);
    actions.appendChild(approveBtn);
  }

  card.appendChild(actions);
  container.appendChild(card);
}

function resumeTask(taskId, decision, notes) {
  fetch(`/api/tasks/${taskId}/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Sovereign-Role': appState.currentRole
    },
    body: JSON.stringify({ decision, notes })
  })
  .then(res => res.json())
  .then(() => {
    const card = document.getElementById(`hitl-${taskId}`);
    if (card) card.remove();
  })
  .catch(err => console.error('Resume failed:', err));
}

function renderNetworkEvent(event) {
  const tbody = document.getElementById('network-events-body');
  if (!tbody) return;

  const emptyRow = tbody.querySelector('.table-empty-row');
  if (emptyRow) emptyRow.remove();

  appState.networkCounters.total += 1;
  if (event.verdict === 'ALLOW') {
    appState.networkCounters.allowed += 1;
  } else {
    appState.networkCounters.denied += 1;
  }

  document.getElementById('counter-total').textContent = appState.networkCounters.total;
  document.getElementById('counter-allowed').textContent = appState.networkCounters.allowed;
  document.getElementById('counter-denied').textContent = appState.networkCounters.denied;

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

  // Limit table rows to 50
  while (tbody.children.length > 50) {
    tbody.removeChild(tbody.lastChild);
  }
}
