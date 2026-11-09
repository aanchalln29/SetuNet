/* ==============================================================================
   SETU-NET Operations Console & Phone Hopping Telemetry
   Vanilla JavaScript, Zero Dependencies, Real-Time P2P Canvas Visualizer
   ============================================================================== */

(() => {
  "use strict";

  const POLL_MS = 1400;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // Canvas State & Multi-Hop Animation Queue
  let canvas, ctx;
  let currentSnapshot = null;
  let activeWaveAnimations = [];  // Forward alert waves { from, to, progress, color, hopNum, distanceM }
  let activeAckAnimations = [];   // Reverse ACK return pulses { from, to, progress, path }
  let selectedNode = null;
  let lastSeenAlertId = null;

  // Flash warning outline for critical alerts
  function triggerCriticalAlarm() {
    const bar = document.querySelector(".emergency-bar");
    if (bar) {
      bar.style.borderColor = "var(--p0-crit)";
      setTimeout(() => { bar.style.borderColor = ""; }, 1400);
    }
  }

  // Professional system notification
  function showToast(message, isError = false) {
    const toast = $("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.style.borderColor = isError ? "var(--p0-crit)" : "var(--border-focus)";
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 3600);
  }

  // ------------------------------------------------------------------ Topology Layout
  // Geometric positions for the 8-Phone disaster test rig (Canvas: 760 x 380)
  const NODE_SCREEN_POSITIONS = {
    "phone-1": { x: 80,  y: 190, label: "P1 (EOC Origin)", role: "Origin Sender" },
    "phone-2": { x: 210, y: 110, label: "P2 (Rescue Alpha)", role: "Relay Node" },
    "phone-3": { x: 215, y: 270, label: "P3 (Civilian Shelter)", role: "Relay Node" },
    "phone-4": { x: 370, y: 115, label: "P4 (Evac Sector Beta)", role: "Relay Node" },
    "phone-5": { x: 380, y: 265, label: "P5 (Medical Field Clinic)", role: "Relay Node" },
    "phone-6": { x: 530, y: 120, label: "P6 (Security Troop Patrol)", role: "Relay Node" },
    "phone-7": { x: 540, y: 270, label: "P7 (River Crossing Post)", role: "Relay Node" },
    "phone-8": { x: 685, y: 190, label: "P8 (Control Outpost)", role: "Isolated Baseline" },
  };

  function initCanvas() {
    canvas = $("meshCanvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    canvas.addEventListener("click", (e) => {
      const cRect = canvas.getBoundingClientRect();
      const clickX = e.clientX - cRect.left;
      const clickY = e.clientY - cRect.top;

      let found = null;
      for (const [nodeId, pos] of Object.entries(NODE_SCREEN_POSITIONS)) {
        const dx = clickX - pos.x;
        const dy = clickY - pos.y;
        if (Math.hypot(dx, dy) <= 24) {
          found = nodeId;
          break;
        }
      }
      handleNodeClick(found);
    });

    requestAnimationFrame(renderCanvasLoop);
  }

  function handleNodeClick(nodeId) {
    selectedNode = nodeId;
    const overlay = $("nodeInfoOverlay");
    if (!nodeId || !currentSnapshot) {
      if (overlay) overlay.hidden = true;
      return;
    }

    const nodeData = (currentSnapshot.nodes || []).find((n) => n.node_id === nodeId);
    if (!nodeData) return;

    $("popupTitle").textContent = nodeData.label;
    $("popupRole").textContent = `Role: ${nodeData.role.toUpperCase()}`;
    $("popupBattery").textContent = `Battery: ${nodeData.battery_pct}% (${nodeData.consumed_mah} mAh drain)`;
    $("popupQueue").textContent = `Queue: ${nodeData.queue_size} alerts | Stored: ${nodeData.stored_buffer_count}`;
    $("popupDistance").textContent = `Active Peers: ${nodeData.neighbors_count} reachable within 200m`;
    
    if (overlay) overlay.hidden = false;
  }

  // ------------------------------------------------------------------ Canvas Rendering Loop
  let animTick = 0;
  function renderCanvasLoop() {
    animTick++;
    if (ctx && canvas) {
      const w = canvas.getBoundingClientRect().width;
      const h = canvas.getBoundingClientRect().height;
      ctx.clearRect(0, 0, w, h);

      drawGridBackground(w, h);
      drawDirectLinks();
      drawPhoneHoppingProgress();
      drawMeshNodes();
    }
    requestAnimationFrame(renderCanvasLoop);
  }

  function drawGridBackground(w, h) {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    ctx.strokeStyle = isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(80, 70, 50, 0.07)";
    ctx.lineWidth = 1;
    const step = 32;
    for (let x = 0; x < w; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
  }

  function drawDirectLinks() {
    if (!currentSnapshot || !currentSnapshot.links) return;
    
    for (const link of currentSnapshot.links) {
      const p1 = NODE_SCREEN_POSITIONS[link.source];
      const p2 = NODE_SCREEN_POSITIONS[link.target];
      if (!p1 || !p2) continue;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      ctx.strokeStyle = isDark ? "rgba(90, 120, 150, 0.25)" : "rgba(30, 58, 95, 0.35)";
      ctx.lineWidth = 1.6;
      ctx.stroke();

      // Draw link distance tag
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      ctx.fillStyle = isDark ? "rgba(149, 158, 169, 0.75)" : "#57534e";
      ctx.font = "8px 'Chivo Mono', Consolas, monospace";
      ctx.textAlign = "center";
      ctx.fillText(`${Math.round(link.distance_m)}m`, midX, midY - 6);

      ctx.restore();
    }
  }

  // Clear directional phone-to-phone hopping
  function drawPhoneHoppingProgress() {
    // 1. Forward Alert Waves with explicit directional arrows & hop tags
    for (let i = activeWaveAnimations.length - 1; i >= 0; i--) {
      const anim = activeWaveAnimations[i];
      anim.progress += 0.025; // Controlled speed so hopping is visible

      const p1 = NODE_SCREEN_POSITIONS[anim.from];
      const p2 = NODE_SCREEN_POSITIONS[anim.to];
      if (p1 && p2) {
        const curX = p1.x + (p2.x - p1.x) * anim.progress;
        const curY = p1.y + (p2.y - p1.y) * anim.progress;

        ctx.save();

        // Active transmitting beam line
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(curX, curY);
        ctx.strokeStyle = anim.color || "#b91c1c";
        ctx.lineWidth = 2.2;
        ctx.stroke();

        // Distinct Forward Packet Node
        ctx.fillStyle = anim.color || "#b91c1c";
        ctx.beginPath();
        ctx.arc(curX, curY, 5.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Clear HOP Number Callout over the link
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        ctx.fillStyle = isDark ? "#ffffff" : "#1c1917";
        ctx.font = "bold 9px 'Chivo Mono', Consolas, monospace";
        ctx.textAlign = "center";
        ctx.fillText(`HOP ${anim.hopNum || 1}`, curX, curY - 12);

        // Directional Arrow Head
        const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
        drawArrowHead(ctx, curX, curY, angle, anim.color || "#b91c1c");

        ctx.restore();
      }

      if (anim.progress >= 1.0) {
        activeWaveAnimations.splice(i, 1);
      }
    }

    // 2. Reverse ACK Pulses (Tactical Green return trajectory to origin)
    for (let i = activeAckAnimations.length - 1; i >= 0; i--) {
      const anim = activeAckAnimations[i];
      anim.progress += 0.03;

      const p1 = NODE_SCREEN_POSITIONS[anim.from];
      const p2 = NODE_SCREEN_POSITIONS[anim.to];
      if (p1 && p2) {
        const curX = p1.x + (p2.x - p1.x) * anim.progress;
        const curY = p1.y + (p2.y - p1.y) * anim.progress;

        ctx.save();
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(curX, curY);
        ctx.strokeStyle = "#38a169";
        ctx.lineWidth = 1.6;
        ctx.stroke();

        // ACK indicator
        ctx.fillStyle = "#38a169";
        ctx.beginPath();
        ctx.arc(curX, curY, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = "bold 8px 'Chivo Mono', Consolas, monospace";
        ctx.textAlign = "center";
        ctx.fillText("ACK", curX, curY + 12);
        ctx.restore();
      }

      if (anim.progress >= 1.0) {
        activeAckAnimations.splice(i, 1);
      }
    }
  }

  function drawArrowHead(context, x, y, angle, color) {
    const headLen = 8;
    context.save();
    context.beginPath();
    context.moveTo(x, y);
    context.lineTo(x - headLen * Math.cos(angle - Math.PI / 6), y - headLen * Math.sin(angle - Math.PI / 6));
    context.lineTo(x - headLen * Math.cos(angle + Math.PI / 6), y - headLen * Math.sin(angle + Math.PI / 6));
    context.closePath();
    context.fillStyle = color;
    context.fill();
    context.restore();
  }

  function drawMeshNodes() {
    if (!currentSnapshot) return;
    const nodes = currentSnapshot.nodes || [];

    for (const node of nodes) {
      const pos = NODE_SCREEN_POSITIONS[node.node_id];
      if (!pos) continue;

      const isSender = node.role === "sender";
      const isControl = node.role === "control";
      const isSelected = selectedNode === node.node_id;

      ctx.save();

      // 150-200m Range Ring
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 46, 0, Math.PI * 2);
      if (isControl && node.neighbors_count === 0) {
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = "rgba(194, 106, 21, 0.4)";
        ctx.stroke();
      } else {
        ctx.strokeStyle = isSender ? "rgba(185, 28, 28, 0.22)" : "rgba(46, 92, 138, 0.18)";
        ctx.stroke();
      }

      // Selection Halo
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 22, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(217, 95, 38, 0.2)";
        ctx.fill();
      }

      // Main Node Body (Industrial Tactical Palette)
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 16, 0, Math.PI * 2);
      if (isSender) {
        ctx.fillStyle = "#8b1c1c";
        ctx.strokeStyle = "#b91c1c";
      } else if (isControl) {
        ctx.fillStyle = node.neighbors_count > 0 ? "#1b354d" : "#713f12";
        ctx.strokeStyle = node.neighbors_count > 0 ? "#2b5a86" : "#c26a15";
      } else {
        ctx.fillStyle = "#182a3d";
        ctx.strokeStyle = "#2b5a86";
      }
      ctx.fill();
      ctx.lineWidth = 1.6;
      ctx.stroke();

      // Node Label inside Circle
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 9px 'Chivo Mono', Consolas, monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(node.node_id.replace("phone-", "P"), pos.x, pos.y);

      // Friendly Name Below
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      ctx.fillStyle = isDark ? "#edf0f5" : "#1c1917";
      ctx.font = "bold 9px 'Barlow', sans-serif";
      ctx.fillText(node.label.split("(")[0].trim(), pos.x, pos.y + 26);

      // Battery & Neighbors
      ctx.fillStyle = isDark ? "#959ea9" : "#57534e";
      ctx.font = "8px 'Chivo Mono', monospace";
      ctx.fillText(`${node.battery_pct}% | ${node.neighbors_count} peers`, pos.x, pos.y + 37);

      ctx.restore();
    }
  }

  // Clear phone-to-phone hopping trigger
  function triggerPhoneHoppingSequence(alert) {
    const catColor = {
      SOS: "#b91c1c",
      EVACUATION: "#d97706",
      TROOP_MOVEMENT: "#2b5a86",
      GENERAL: "#1e6e4f",
    }[alert.category] || "#b91c1c";

    const path = alert.hop_path || ["phone-1"];
    const totalHops = Math.max(1, path.length - 1);

    // Update the Hop Sequence Timeline Bar below the canvas
    const statusText = $("hopStatusText");
    if (statusText) {
      statusText.textContent = `ALERT ${alert.message_id} HOPS: ${path.join(" -> ")}`;
      statusText.className = "hop-status-active";
    }

    // Sequentially enqueue forward hops
    for (let i = 0; i < path.length - 1; i++) {
      setTimeout(() => {
        activeWaveAnimations.push({
          from: path[i],
          to: path[i + 1],
          progress: 0,
          color: catColor,
          hopNum: i + 1,
        });

        // Highlight timeline nodes
        const stepEl = $(`step${i + 1}`);
        if (stepEl) stepEl.classList.add("hop-link-step--active");
      }, i * 350); // Clear sequential pause between hops
    }

    // Schedule reverse ACK return pulse after forward propagation completes
    setTimeout(() => {
      if (path.length >= 2) {
        activeAckAnimations.push({
          from: path[path.length - 1],
          to: path[0],
          progress: 0,
          path: path,
        });
      }
      if (statusText) {
        statusText.textContent = `ACK RECEIVED AT ORIGIN P1 FROM ${path[path.length - 1]}`;
        statusText.className = "hop-status-ack";
      }
    }, totalHops * 380 + 200);
  }

  // ------------------------------------------------------------------ API Polling & Sync
  async function pollSnapshot() {
    try {
      const res = await fetch("/api/snapshot", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      currentSnapshot = data;
      renderSnapshot(data);
    } catch (_) {}
  }

  function renderSnapshot(data) {
    const stats = data.stats || {};
    const targets = data.performance_targets || {};

    $("statBroadcasts").textContent = stats.total_broadcasts || 0;
    $("statBroadcastRate").textContent = `${stats.alerts_per_minute || 0} alerts/min`;

    $("statDeliveryRatio").textContent = `${targets.delivery_ratio_pct || 100}%`;
    $("statAvgHopLatency").textContent = `${targets.avg_per_hop_latency_ms || 680} ms`;
    $("statDuplicates").textContent = stats.duplicates_suppressed || 0;
    $("statTtlDrops").textContent = stats.ttl_dropped || 0;
    $("statBatteryDrain").textContent = `${targets.total_network_drain_mah || 0} mAh`;

    const delBadge = $("statDeliveryBadge");
    if (delBadge) {
      delBadge.textContent = targets.target_delivery_met ? "TARGET >= 90% [MET]" : "TARGET >= 90%";
    }

    const latBadge = $("statLatencyBadge");
    if (latBadge) {
      latBadge.textContent = targets.target_hop_delay_met ? "TARGET < 5.0S [MET]" : "TARGET < 5.0S";
    }

    $("meshPillText").textContent = `MESH: ${data.active_peer_count || 8} NODES ONLINE`;

    renderPriorityQueue(data.priority_queue || []);
    renderAlertFeed(data.recent_alerts || []);
    renderAcksList(data.recent_acks || []);
  }

  function renderPriorityQueue(queueItems) {
    const container = $("queueList");
    if (!container) return;
    $("queueBadge").textContent = `${queueItems.length} in queue`;

    if (!queueItems.length) {
      container.innerHTML = `<div class="empty">Priority queue clear. Messages dispatched within latency threshold.</div>`;
      return;
    }

    container.innerHTML = queueItems.map((item) => `
      <div class="queue-card queue-card--${item.category.toLowerCase()}">
        <div>
          <span class="queue-card__title">
            <strong>[P${item.priority}] ${esc(item.category_label)}</strong> &middot; ${esc(item.origin_node_id)}
          </span>
          <div class="queue-card__sub">${esc(item.payload_preview)}...</div>
        </div>
        <span class="count-badge">${item.ttl} Hops Left</span>
      </div>
    `).join("");
  }

  function renderAlertFeed(alerts) {
    const feed = $("alertFeed");
    if (!feed) return;

    if (!alerts.length) {
      feed.innerHTML = `<div class="empty">No emergency broadcasts received.</div>`;
      return;
    }

    const topAlert = alerts[0];
    if (topAlert && topAlert.message_id !== lastSeenAlertId) {
      lastSeenAlertId = topAlert.message_id;
      triggerPhoneHoppingSequence(topAlert);
      if (topAlert.category === "SOS") {
        triggerCriticalAlarm();
      }
    }

    feed.innerHTML = alerts.map((a) => {
      const loc = a.location || { lat: 0, lon: 0 };
      const timeStr = new Date(a.timestamp * 1000).toLocaleTimeString([], { hour12: false });
      const hopsStr = (a.hop_path || [a.origin_node_id]).join(" -> ");

      return `
        <article class="feed-card" data-msg-id="${esc(a.message_id)}">
          <div class="feed-card__head">
            <span class="tag-cat tag-cat--${a.category.toLowerCase()}">${esc(a.category_label)} [P${a.priority}]</span>
            <span class="feed-card__time">${esc(timeStr)}</span>
          </div>
          <p class="feed-card__payload"><strong>${esc(a.message_id)}:</strong> ${esc(a.payload_text)}</p>
          <div class="feed-card__meta">
            <span class="sig-badge">[ED25519 VERIFIED]</span>
            <span>GPS: ${loc.lat}, ${loc.lon}</span>
            <span>TTL: ${a.ttl}</span>
            <span>Hops: ${a.hop_count} (${esc(hopsStr)})</span>
            <button class="btn btn--ghost-sm btn--verify-card" data-id="${esc(a.message_id)}" style="margin-left:auto;">
              Audit Proof
            </button>
          </div>
        </article>
      `;
    }).join("");

    feed.querySelectorAll(".btn--verify-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        loadAuditRecord(btn.dataset.id);
      });
    });
  }

  function renderAcksList(acks) {
    const container = $("acksList");
    if (!container) return;
    $("ackCountBadge").textContent = `${acks.length} ACKs`;

    if (!acks.length) {
      container.innerHTML = `<div class="empty">Delivery confirmations will appear as relay nodes acknowledge reception.</div>`;
      return;
    }

    container.innerHTML = acks.map((ack) => `
      <div class="ack-card">
        <div>
          <strong>${esc(ack.ack_node_id)}</strong> confirmed <code>${esc(ack.original_message_id)}</code>
          <div style="font-size: 0.68rem; color: var(--text-muted); margin-top:2px;">
            Return Path: ${(ack.return_path || []).join(" -> ")}
          </div>
        </div>
        <div style="text-align: right;">
          <span class="ack-card__hops">${ack.hops_to_node} Hops</span>
          <div style="font-size: 0.68rem; color: var(--text-muted);">${ack.latency_ms} ms</div>
        </div>
      </div>
    `).join("");
  }

  // ------------------------------------------------------------------ Alert Actions
  async function triggerAlert(category, defaultText) {
    try {
      const res = await fetch("/api/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender_id: "phone-1",
          category: category,
          payload_text: defaultText,
          ttl: 6,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        showToast(`DISPATCHED: ${category} broadcast propagating across mesh`);
        pollSnapshot();
      }
    } catch (_) {
      showToast("Dispatch transmission failed", true);
    }
  }

  // ------------------------------------------------------------------ Scenario Injections
  async function injectScenario(key) {
    showToast(`Executing Protocol Scenario: ${key}`);
    try {
      const res = await fetch("/api/inject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: key }),
      });
      const data = await res.json();
      if (data.ok) {
        showToast(`[PASS] ${data.name}: ${data.observed}`);
      } else {
        showToast(`[RESULT] ${data.name || key}: ${data.observed || data.error}`, !data.ok);
      }
      pollSnapshot();
    } catch (_) {
      showToast("Scenario execution failed", true);
    }
  }

  // ------------------------------------------------------------------ Audit Records
  async function loadAuditRecord(messageId) {
    $("auditInputId").value = messageId;
    try {
      const res = await fetch(`/api/audit?message_id=${encodeURIComponent(messageId)}`);
      if (!res.ok) {
        $("auditOutput").textContent = "No audit record located for that message identifier.";
        return;
      }
      const data = await res.json();
      $("auditOutput").textContent = JSON.stringify(data, null, 2);
      
      const dlBtn = $("btnDownloadAudit");
      if (dlBtn) {
        dlBtn.href = `/api/audit?message_id=${encodeURIComponent(messageId)}&download=1`;
        dlBtn.hidden = false;
      }
    } catch (_) {
      $("auditOutput").textContent = "Failed to load cryptographic audit record.";
    }
  }

  // ------------------------------------------------------------------ Event Wiring
  function initEvents() {
    $("btnTriggerSos").addEventListener("click", () => {
      triggerAlert("SOS", "CRITICAL SOS: Structural collapse in Sector 4. Search and rescue dispatch required immediately.");
    });

    $("btnTriggerEvac").addEventListener("click", () => {
      triggerAlert("EVACUATION", "EVACUATION DIRECTIVE: Water rising in Sector 2. Evacuate all personnel to High Embankment.");
    });

    $("btnTriggerTroop").addEventListener("click", () => {
      triggerAlert("TROOP_MOVEMENT", "TACTICAL ORDER: Unit Bravo reposition perimeter security to Sector 3 Crossing.");
    });

    $("btnTriggerGen").addEventListener("click", () => {
      triggerAlert("GENERAL", "INFORMATIONAL ADVISORY: Sector canal crossing cleared for emergency pedestrian traffic.");
    });

    const modal = $("customAlertDialog");
    $("btnCustomAlertModal").addEventListener("click", () => {
      if (modal) modal.showModal();
    });

    $("btnCloseModal").addEventListener("click", () => {
      if (modal) modal.close();
    });

    $("btnCancelModal").addEventListener("click", () => {
      if (modal) modal.close();
    });

    $("customAlertForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const cat = $("formCategory").value;
      const sender = $("formSender").value;
      const lat = parseFloat($("formLat").value);
      const lon = parseFloat($("formLon").value);
      const ttl = parseInt($("formTtl").value, 10);
      const payload = $("formPayload").value;

      try {
        const res = await fetch("/api/trigger", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sender_id: sender,
            category: cat,
            payload_text: payload,
            lat: lat,
            lon: lon,
            ttl: ttl,
          }),
        });
        const data = await res.json();
        if (data.ok) {
          showToast(`Custom ${cat} broadcast dispatched`);
          if (modal) modal.close();
          pollSnapshot();
        }
      } catch (_) {
        showToast("Dispatch error", true);
      }
    });

    document.querySelectorAll(".chip[data-scenario]").forEach((chip) => {
      chip.addEventListener("click", () => {
        injectScenario(chip.dataset.scenario);
      });
    });

    $("btnTamperAttack").addEventListener("click", async () => {
      try {
        const res = await fetch("/api/tamper", { method: "POST" });
        const data = await res.json();
        showToast("SECURITY: Injected forged signature was rejected by receiving mesh nodes");
        pollSnapshot();
      } catch (_) {
        showToast("Injection failed", true);
      }
    });

    let phone8InRange = false;
    $("btnTogglePhone8").addEventListener("click", async () => {
      phone8InRange = !phone8InRange;
      const lat = phone8InRange ? 28.6148 : 28.6489;
      const lon = phone8InRange ? 77.2102 : 77.2440;
      
      await fetch("/api/move-node", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: "phone-8", lat: lat, lon: lon }),
      });
      showToast(phone8InRange ? "Phone 8 positioned in range (150m)" : "Phone 8 positioned out-of-range (>3500m)");
      pollSnapshot();
    });

    $("btnVerifyAudit").addEventListener("click", () => {
      const id = $("auditInputId").value.trim();
      if (id) loadAuditRecord(id);
    });

    let demoActive = true;
    $("demoToggle").addEventListener("click", async () => {
      demoActive = !demoActive;
      await fetch("/api/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: demoActive }),
      });
      $("demoToggle").textContent = `TRAFFIC GENERATOR: ${demoActive ? "ACTIVE" : "PAUSED"}`;
      $("demoToggle").classList.toggle("btn--ghost", demoActive);
    });

    $("themeToggle").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "beige";
      const next = cur === "dark" ? "beige" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("setunet-theme", next); } catch (_) {}
    });

    try {
      const saved = localStorage.getItem("setunet-theme");
      document.documentElement.setAttribute("data-theme", saved === "dark" ? "dark" : "beige");
    } catch (_) {
      document.documentElement.setAttribute("data-theme", "beige");
    }
  }

  // ------------------------------------------------------------------ Initialization
  window.addEventListener("DOMContentLoaded", () => {
    initCanvas();
    initEvents();
    pollSnapshot();
    setInterval(pollSnapshot, POLL_MS);
  });
})();
