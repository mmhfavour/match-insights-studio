/* Producer desk: human-in-the-loop control over what the AI puts to air. */
(function () {
  const $ = (id) => document.getElementById(id);
  const S = { proposals: new Map(), audit: [], metrics: {}, match: null };
  let ws;

  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function send(m) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(m)); }

  const TILE = [["proposed", "Proposed"], ["aired", "Aired"], ["approved", "Approved by you"], ["auto_approved", "Auto-aired"],
    ["edited", "Edited"], ["rejected", "Rejected"], ["verifier_rejections", "Verifier catches"], ["template_fallbacks", "Template fallbacks"],
    ["avg_draft_latency_ms", "Avg draft ms"]];
  function renderMetrics() {
    const m = S.metrics;
    $("tiles").innerHTML = TILE.map(([k, l]) => `<div><b>${m[k] ?? 0}</b><span>${l}</span></div>`).join("");
    $("agentMode").textContent = m.agents ? `agents: ${m.agents} · ${m.state || ""} · ${m.speed || ""}×` : "";
    $("autoChk").checked = !!m.auto;
    for (const b of $("speedSeg").children) b.setAttribute("aria-pressed", String(Number(b.dataset.v) === m.speed));
  }

  function evidenceLine(ev) {
    return Object.entries(ev).filter(([, v]) => typeof v === "number" || typeof v === "string").slice(0, 8)
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ");
  }

  function renderQueue() {
    const list = [...S.proposals.values()].reverse().slice(0, 30);
    if (!list.length) return;
    // Keep anything the producer has typed, and their cursor, across re-renders.
    const focusId = document.activeElement && document.activeElement.id;
    document.querySelectorAll(".prop.pending").forEach((card) => {
      const p = S.proposals.get(card.dataset.id);
      if (p) p.edit = { headline: $(`h-${p.moment.id}`).value, body: $(`b-${p.moment.id}`).value };
    });
    $("queue").innerHTML = list.map((p) => {
      const m = p.moment, d = p.draft, shown = p.status === "pending" && p.edit ? p.edit : d;
      const src = d.source === "foundry" ? '<span class="badge ai">Foundry agent</span>' : '<span class="badge">Template</span>';
      const ver = (d.verifier || []).length ? `<span class="badge no" title="${esc(d.verifier.join("; "))}">Verifier: ${d.verifier.length} issue(s), template used</span>` : '<span class="badge ok">Verified</span>';
      const status = p.status === "pending" ? `<span class="count" data-auto="${p.auto_at || ""}"></span>` : `<span class="badge ${p.status === "approved" ? "ok" : "no"}">${p.status}</span>`;
      const disabled = p.status !== "pending" ? "disabled" : "";
      return `<article class="prop ${p.status}" data-id="${m.id}">
        <div class="top"><span class="m">${esc(m.minute)}</span><span class="t">${esc(m.type.replace(/_/g, " "))}</span>${src}${ver}<span class="badge">importance ${m.importance}</span><span class="badge">${esc(m.audiences.join(" / "))}</span>${status}</div>
        <input id="h-${m.id}" value="${esc(shown.headline)}" ${disabled} aria-label="Headline">
        <textarea id="b-${m.id}" ${disabled} aria-label="Body">${esc(shown.body)}</textarea>
        <div class="ev">${esc(evidenceLine(m.evidence))}</div>
        ${p.status === "pending" ? `<div class="acts"><button class="btn primary" type="button" data-a="approve">Approve</button><button class="btn" type="button" data-a="edit">Air my edit</button><button class="btn danger" type="button" data-a="reject">Reject</button></div>` : ""}
      </article>`;
    }).join("");
    if (focusId && $(focusId)) $(focusId).focus();
  }
  $("queue").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-a]"); if (!b) return;
    const id = b.closest(".prop").dataset.id, a = b.dataset.a;
    const msg = { type: "decision", moment_id: id, action: a };
    if (a === "edit") { msg.headline = $(`h-${id}`).value; msg.body = $(`b-${id}`).value; }
    send(msg);
  });
  // Typing in a pending card pauses its auto-air countdown, so a producer is never overruled mid-edit.
  $("queue").addEventListener("focusin", (e) => {
    if (e.target.matches("input, textarea") && S.metrics.auto) { send({ type: "auto", enabled: false }); }
  });

  function renderAudit() {
    const rows = S.audit.slice(-200).reverse();
    $("auditCount").textContent = `${S.audit.length} entries`;
    $("audit").innerHTML = rows.map((a) => `<tr><td class="mono">${esc(a.minute)}</td><td>${esc(a.action)}${a.source ? ` <span class="badge ${a.source === "foundry" ? "ai" : ""}">${esc(a.source)}</span>` : ""}</td><td>${esc(a.by)}</td><td>${esc(a.type.replace(/_/g, " "))}${a.headline ? `<br><span class="meta">${esc(a.headline)}</span>` : ""}${a.reason ? `<br><span class="meta">${esc(a.reason)}</span>` : ""}</td></tr>`).join("");
  }

  setInterval(() => {
    const now = Date.now() / 1000;
    document.querySelectorAll(".count[data-auto]").forEach((el) => {
      const at = Number(el.dataset.auto);
      el.textContent = at && S.metrics.auto ? `Auto-air in ${Math.max(0, Math.ceil(at - now))} s` : "Waiting for you";
    });
  }, 250);

  document.querySelectorAll("[data-c]").forEach((b) => b.addEventListener("click", () => send({ type: "control", action: b.dataset.c })));
  $("speedSeg").addEventListener("click", (e) => { const v = Number(e.target.closest("button")?.dataset.v); if (v) send({ type: "control", action: "speed", speed: v }); });
  $("autoChk").addEventListener("change", (e) => send({ type: "auto", enabled: e.target.checked, delay: Number($("autoDelay").value) }));
  $("autoDelay").addEventListener("change", () => send({ type: "auto", enabled: $("autoChk").checked, delay: Number($("autoDelay").value) }));

  function connect() {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/producer`);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "hello") {
        S.match = msg.match; S.metrics = msg.metrics; S.audit = msg.audit; S.proposals.clear();
        msg.proposals.forEach((p) => S.proposals.set(p.moment.id, p));
        if (msg.snapshot) setScore(msg.snapshot);
        renderMetrics(); renderQueue(); renderAudit();
      } else if (msg.type === "proposal") {
        S.proposals.set(msg.proposal.moment.id, msg.proposal); S.audit.push(msg.audit); S.metrics = msg.metrics;
        renderQueue(); renderAudit(); renderMetrics();
      } else if (msg.type === "decision") {
        const p = S.proposals.get(msg.moment_id); if (p) p.status = msg.status;
        S.audit.push(msg.audit); S.metrics = msg.metrics; renderQueue(); renderAudit(); renderMetrics();
      } else if (msg.type === "metrics") { S.metrics = msg.metrics; renderMetrics(); }
      else if (msg.type === "stats") setScore(msg.stats);
      else if (msg.type === "state") { S.metrics.state = msg.state; S.metrics.speed = msg.speed; renderMetrics(); }
      else if (msg.type === "reset") { S.proposals.clear(); S.audit = []; $("queue").innerHTML = '<div class="empty">New match. Waiting for the first moment.</div>'; renderAudit(); }
    };
    ws.onclose = () => setTimeout(connect, 2000);
  }
  function setScore(snap) {
    if (!S.match) return;
    const h = S.match.home, a = S.match.away;
    $("score").textContent = `${h.short} ${snap.score[h.code]}-${snap.score[a.code]} ${a.short} · ${snap.minute}`;
  }
  connect();
})();
