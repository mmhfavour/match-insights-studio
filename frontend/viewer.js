/* Viewer: renders the feed, the on-pitch graphics and the analyst rail.
   Two sources feed the same UI:
     live   - WebSocket to the server (/ws/viewer); overlays arrive already personalized.
     static - window.MIS_TIMELINE, a pre-built match with every overlay variant (used by the demo build). */
(function () {
  const $ = (id) => document.getElementById(id);
  const TL = window.MIS_TIMELINE || null;
  const STATIC = !!TL;

  const LABELS = {
    goal: { en: "Goal", hi: "गोल", ta: "கோல்" },
    big_chance: { en: "Big chance", hi: "बड़ा मौका", ta: "பெரிய வாய்ப்பு" },
    press_shift: { en: "Pressing", hi: "प्रेसिंग", ta: "அழுத்தம்" },
    momentum_swing: { en: "Momentum", hi: "मोमेंटम", ta: "உத்வேகம்" },
    rhythm_shift: { en: "Game rhythm", hi: "खेल की लय", ta: "ஆட்ட ரிதம்" },
    card: { en: "Card", hi: "कार्ड", ta: "அட்டை" },
    top_speed: { en: "Top speed", hi: "टॉप स्पीड", ta: "அதிகபட்ச வேகம்" },
    rocket_shot: { en: "Shot speed", hi: "शॉट स्पीड", ta: "ஷாட் வேகம்" },
    line_breaker: { en: "Pass quality", hi: "पास क्वालिटी", ta: "பாஸ் தரம்" },
    distance_milestone: { en: "Workrate", hi: "मेहनत", ta: "உழைப்பு" },
    substitution: { en: "Substitution", hi: "बदलाव", ta: "மாற்றம்" },
    pass_milestone: { en: "Milestone", hi: "उपलब्धि", ta: "மைல்கல்" },
    half_time: { en: "Half-time", hi: "हाफ़-टाइम", ta: "இடைவேளை" },
    full_time: { en: "Full-time", hi: "फ़ुल-टाइम", ta: "ஆட்ட முடிவு" },
  };
  const WHY = { en: "Why?", hi: "क्यों?", ta: "ஏன்?" };
  const EV_LABELS = {
    xg: "xG", xg_pct: "Chance converts (%)", shot_speed_kmh: "Shot speed (km/h)", distance_m: "Distance (m)",
    chain_passes: "Passes in move", chain_seconds: "Move duration (s)", score_home: "Home score", score_away: "Away score",
    press_rate_now: "Press rate now", press_rate_before: "Press rate, match baseline", change_pct: "Change (%)",
    ppda_now: "PPDA, last 10 min", ppda_before: "PPDA before", threat_share_now: "Threat share now (%)",
    threat_share_before: "Threat share before (%)", possession_10min: "Possession, last 10 min (%)",
    top_speed_kmh: "Top speed (km/h)", sprint_distance_m: "Sprint distance (m)", threshold_kmh: "Tag threshold (km/h)",
    difficulty: "Pass difficulty (0-1)", progressive_m: "Progress (m)", ball_speed_kmh: "Ball speed (km/h)",
    team_xg: "Team xG so far", off_distance_km: "Distance covered (km)", distance_km: "Distance (km)",
    why_tags: "Why tags", related_summary: "Linked moment", index_now: "Control index now", index_before: "Control index before",
    switches_per_min_now: "Possession changes/min", avg_chain_now: "Average move (passes)",
  };

  const S = {
    match: null, profile: { mode: "analyst", lang: "en", club: "", player: "" },
    snapshot: null, series: [], aired: [], speed: 30, playing: true, t: 0, state: "ready",
    slots: { lower_third: null, stat_card: null, player_tag: null, full_card: null },
    queue: [], agents: "templates",
  };
  try { Object.assign(S.profile, JSON.parse(localStorage.getItem("mis-profile") || "{}")); } catch (e) { /* storage unavailable */ }

  let pitch = null;

  // ------------------------------------------------------------------ profile + copy
  function staticKey(mode, lang, club) { return `${mode}|${lang}|${mode === "casual" && club ? club : "-"}`; }
  function wants(m) {
    const mode = S.profile.mode;
    if (!m.audiences.includes(mode)) return false;
    if (mode === "player") return ["goal", "half_time", "full_time"].includes(m.type) || m.players.includes(S.profile.player);
    return true;
  }
  function staticRecord(m) {
    const v = TL.overlays[m.id];
    const mode = S.profile.mode === "player" ? "analyst" : S.profile.mode;
    const copy = v[staticKey(mode, S.profile.lang, S.profile.club)] || v[staticKey("analyst", "en", "")];
    const graphic = {};
    for (const [k, val] of Object.entries(m.evidence)) if (typeof val === "number") graphic[k] = val;
    return { id: `${m.id}|${staticKey(mode, S.profile.lang, S.profile.club)}`, moment_id: m.id, type: m.type, slot: m.slot,
      t_in: m.t, duration_s: m.duration_s, clock: m.clock, minute: m.minute, priority: m.importance, team: m.team,
      players: m.players, audiences: m.audiences, headline: copy.headline, body: copy.body, source: "template",
      verifier: [], graphic, evidence: m.evidence, context: m.context };
  }
  function saveProfile() { try { localStorage.setItem("mis-profile", JSON.stringify(S.profile)); } catch (e) { /* ignore */ } }

  function setProfile(patch) {
    Object.assign(S.profile, patch);
    if (S.profile.mode === "player" && !S.profile.player) S.profile.player = defaultPlayer();
    saveProfile();
    syncControls();
    if (pitch) pitch.focus = S.profile.mode === "player" ? S.profile.player : null;
    if (STATIC) {
      S.aired = TL.moments.filter((m) => m.t <= S.t).map(staticRecord);
      rerenderVisible();
    } else {
      send({ type: "profile", profile: S.profile });
      refreshLiveHistory();
    }
    renderRail();
    renderMoments();
  }
  function defaultPlayer() {
    const m = S.match; if (!m) return "";
    const club = S.profile.club || m.home.code;
    const side = m.home.code === club ? m.home : m.away;
    const st = side.players.find((p) => p.role === "ST") || side.players[9];
    return st.id;
  }

  function syncControls() {
    for (const b of $("modeSeg").children) b.setAttribute("aria-pressed", String(b.dataset.v === S.profile.mode));
    for (const b of $("langSeg").children) b.setAttribute("aria-pressed", String(b.dataset.v === S.profile.lang));
    for (const b of $("speedSeg").children) b.setAttribute("aria-pressed", String(Number(b.dataset.v) === S.speed));
    $("clubSel").value = S.profile.club || "";
    $("playerField").hidden = S.profile.mode !== "player";
    if (S.profile.player) $("playerSel").value = S.profile.player;
    document.documentElement.lang = S.profile.lang;
  }

  // ------------------------------------------------------------------ match setup
  function setMatch(match) {
    S.match = match;
    const h = match.home, a = match.away;
    $("homeCode").textContent = h.code; $("awayCode").textContent = a.code;
    $("homeChip").style.background = h.color; $("awayChip").style.background = a.color;
    const cs = $("clubSel");
    cs.innerHTML = '<option value="">Neutral</option>' + [h, a].map((t) => `<option value="${t.code}">${esc(t.name)}</option>`).join("");
    const ps = $("playerSel");
    ps.innerHTML = [h, a].map((t) => `<optgroup label="${esc(t.name)}">` +
      t.players.concat(t.bench).map((p) => `<option value="${p.id}">${p.number} · ${esc(p.name)}</option>`).join("") + "</optgroup>").join("");
    if (!pitch) pitch = new window.Pitch($("pitch"), match); else pitch.setMatch(match);
    if (S.profile.mode === "player" && !S.profile.player) S.profile.player = defaultPlayer();
    pitch.focus = S.profile.mode === "player" ? S.profile.player : null;
    document.documentElement.style.setProperty("--home", h.color);
    document.documentElement.style.setProperty("--away", a.color);
    syncControls();
  }

  // ------------------------------------------------------------------ events and stats
  const TICK = {
    pass: (e) => `PASS ${name(e.player)}${e.d && e.d.recipient ? " → " + name(e.d.recipient) : " · lost"}`,
    shot: (e) => `SHOT ${name(e.player)} · xG ${e.d.xg} · ${Math.round(e.d.speed_kmh)} km/h`,
    tackle: (e) => `TACKLE ${name(e.player)}`, interception: (e) => `INTERCEPTION ${name(e.player)}`,
    pressure: (e) => `PRESSURE ${name(e.player)}`, dribble: (e) => `DRIBBLE ${name(e.player)}`,
    sprint: (e) => `SPRINT ${name(e.player)} · ${e.d.top_speed_kmh} km/h`, corner: (e) => `CORNER ${e.team}`,
    save: (e) => `SAVE ${name(e.player)}`, foul: (e) => `FOUL ${name(e.player)}`,
  };
  function name(id) {
    if (!id || !S.match) return "";
    for (const s of ["home", "away"]) for (const p of S.match[s].players.concat(S.match[s].bench)) if (p.id === id) return p.short;
    return id;
  }
  function player(id) {
    for (const s of ["home", "away"]) for (const p of S.match[s].players.concat(S.match[s].bench)) if (p.id === id) return p;
    return null;
  }
  function onEvent(ev, instant) {
    pitch.onEvent(ev, instant);
    $("clock").textContent = ev.clock;
    if (ev.type === "goal" && ev.d && ev.d.score) setScore(ev.d.score);
    const f = TICK[ev.type];
    if (f && !instant) $("ticker").textContent = f(ev);
  }
  function setScore(score) {
    $("sh").textContent = score[S.match.home.code]; $("sa").textContent = score[S.match.away.code];
  }
  function onStats(snap) {
    S.snapshot = snap;
    if (snap.series) S.series = snap.series;
    setScore(snap.score);
    $("clock").textContent = snap.clock;
    renderRail();
  }

  // ------------------------------------------------------------------ overlays
  function onOverlay(rec, opts = {}) {
    if (!opts.silent) {
      const i = S.aired.findIndex((r) => r.moment_id === rec.moment_id);
      if (i >= 0) S.aired[i] = rec; else S.aired.push(rec);
      renderMoments();
    }
    if (opts.silent) return;
    show(rec);
  }
  function show(rec) {
    const slot = rec.slot;
    const cur = S.slots[slot];
    if (cur && cur.rec.moment_id === rec.moment_id) { mount(rec); return; }
    if (cur && cur.until > performance.now() && cur.rec.priority > rec.priority && slot !== "full_card") {
      S.queue.push(rec); S.queue = S.queue.slice(-4); return;
    }
    mount(rec);
  }
  function durationMs(rec) {
    const base = { full_card: 9000, lower_third: 7000, stat_card: 7000, player_tag: 5000 }[rec.slot] || 6000;
    return S.speed >= 60 ? base * 0.7 : base;
  }
  function mount(rec) {
    const slot = rec.slot;
    const old = S.slots[slot];
    if (old && old.el) old.el.remove();
    if (slot === "full_card") {
      // A recap card takes the whole screen; clear smaller graphics underneath it.
      for (const k of ["lower_third", "stat_card", "player_tag"]) { if (S.slots[k]) { S.slots[k].el.remove(); S.slots[k] = null; } }
    }
    const el = document.createElement("button");
    el.type = "button";
    el.className = { lower_third: "lower", stat_card: "statcard", player_tag: "ptag", full_card: "fullcard" }[slot] + " enter";
    const kicker = `${rec.minute} · ${(LABELS[rec.type] || {})[S.profile.lang] || rec.type}`;
    const teamColor = rec.team ? (rec.team === S.match.home.code ? S.match.home.color : S.match.away.color) : "var(--accent)";
    if (slot === "lower_third") {
      el.innerHTML = `<span class="stripe" style="background:${teamColor}"></span><span class="txt"><span class="kicker">${esc(kicker)} <span class="why-chip">${WHY[S.profile.lang]}</span></span><span class="head">${esc(rec.headline)}</span><span class="body">${esc(rec.body)}</span></span>`;
    } else if (slot === "stat_card") {
      el.innerHTML = `<span class="kicker">${esc(kicker)}</span><span class="head">${esc(rec.headline)}</span>${numsFor(rec)}<span class="body">${esc(rec.body)}</span>`;
      el.style.borderTop = `3px solid ${teamColor}`;
    } else if (slot === "player_tag") {
      el.innerHTML = `<span class="head">${esc(rec.headline)}</span><span class="body">${esc(rec.body)}</span>`;
    } else {
      el.innerHTML = `<span class="kicker">${esc(kicker)}</span><span class="head">${esc(rec.headline)}</span><span class="body">${esc(rec.body)}</span>`;
    }
    el.addEventListener("click", () => openDrawer(rec));
    el.setAttribute("aria-label", `${rec.headline}. ${rec.body}`);
    $("gfx").appendChild(el);
    S.slots[slot] = { rec, el, until: performance.now() + durationMs(rec) };
    if (pitch) pitch.highlight = new Set(rec.players || []);
    $("feed").classList.toggle("has-lower", !!S.slots.lower_third);
    if (slot === "player_tag") placeTag();
  }
  function numsFor(rec) {
    const g = rec.graphic || {};
    const pick = {
      press_shift: [["press_rate_before", "Baseline"], ["press_rate_now", "Now"], ["change_pct", "Change %"]],
      momentum_swing: [["threat_share_before", "Threat before %"], ["threat_share_now", "Threat now %"]],
      rhythm_shift: [["switches_per_min_before", "Turnovers/min"], ["switches_per_min_now", "Now"], ["avg_chain_now", "Avg move"]],
    }[rec.type];
    if (!pick || S.profile.mode === "casual") return "";
    return `<span class="nums">${pick.filter(([k]) => g[k] != null).map(([k, l]) => `<span><b>${g[k]}</b>${l}</span>`).join("")}</span>`;
  }
  function placeTag() {
    const t = S.slots.player_tag;
    if (!t) return;
    const pid = (t.rec.players || [])[0];
    const f = pid && pitch.screenFrac(pid);
    if (f) { t.el.style.left = `${Math.min(84, Math.max(16, f.x * 100))}%`; t.el.style.top = `${Math.max(16, f.y * 100)}%`; }
    else { t.el.style.left = "50%"; t.el.style.top = "40%"; }
  }
  function tickSlots(now) {
    for (const slot of Object.keys(S.slots)) {
      const cur = S.slots[slot];
      if (cur && cur.until <= now) {
        cur.el.remove(); S.slots[slot] = null;
        const next = S.queue.findIndex((r) => r.slot === slot);
        if (next >= 0) mount(S.queue.splice(next, 1)[0]);
      }
    }
    if (!S.slots.lower_third && !S.slots.stat_card && !S.slots.player_tag && pitch) pitch.highlight = new Set();
    $("feed").classList.toggle("has-lower", !!S.slots.lower_third);
    placeTag();
  }
  function clearSlots() {
    for (const slot of Object.keys(S.slots)) { if (S.slots[slot]) S.slots[slot].el.remove(); S.slots[slot] = null; }
    S.queue = [];
  }
  function rerenderVisible() {
    for (const slot of Object.keys(S.slots)) {
      const cur = S.slots[slot];
      if (!cur) continue;
      const fresh = S.aired.find((r) => r.moment_id === cur.rec.moment_id);
      if (fresh && wantsRec(fresh)) { const until = cur.until; mount(fresh); S.slots[slot].until = until; }
      else { cur.el.remove(); S.slots[slot] = null; }
    }
  }
  function wantsRec(rec) { return wants({ audiences: rec.audiences || ["analyst"], players: rec.players || [], type: rec.type }); }

  // ------------------------------------------------------------------ rail
  function rows(spec) {
    const snap = S.snapshot; if (!snap) return "";
    const h = snap.teams[S.match.home.code], a = snap.teams[S.match.away.code];
    return spec.map(([label, fh, fa, invert]) => {
      const vh = fh(h, snap), va = fa(a, snap);
      let nh = parseFloat(vh) || 0, na = parseFloat(va) || 0;
      if (invert) { nh = nh ? 1 / nh : 0; na = na ? 1 / na : 0; }
      const tot = nh + na || 1;
      return `<div class="row"><span class="v">${vh ?? "-"}</span><span class="lbl">${label}<span class="bar"><i style="width:${(100 * nh) / tot}%"></i><i style="width:${(100 * na) / tot}%"></i></span></span><span class="v">${va ?? "-"}</span></div>`;
    }).join("");
  }
  function renderRail() {
    if (!S.match) return;
    const snap = S.snapshot, sp = $("statsPanel"), fp = $("flowPanel");
    const head = `<div class="teams-head"><span style="color:${S.match.home.color}">${esc(S.match.home.short)}</span><span style="color:${S.match.away.color}">${esc(S.match.away.short)}</span></div>`;
    if (!snap) { sp.innerHTML = `<h2>Match stats</h2><div class="empty">Kick-off is moments away.</div>`; fp.innerHTML = ""; return; }
    const mode = S.profile.mode;
    if (mode === "analyst") {
      sp.innerHTML = `<h2>Match stats <small>${snap.minute}</small></h2>${head}<div class="cmp">${rows([
        ["Possession %", (t, s) => s.possession[S.match.home.code], (t, s) => s.possession[S.match.away.code]],
        ["xG", (t) => t.xg.toFixed(2), (t) => t.xg.toFixed(2)],
        ["Shots (on target)", (t) => `${t.shots} (${t.on_target})`, (t) => `${t.shots} (${t.on_target})`],
        ["Pass accuracy %", (t) => t.pass_accuracy, (t) => t.pass_accuracy],
        ["PPDA (lower = harder press)", (t) => t.ppda ?? "-", (t) => t.ppda ?? "-", true],
        ["Pressures", (t) => t.pressures, (t) => t.pressures],
        ["Final-third entries", (t) => t.final_third_entries, (t) => t.final_third_entries],
        ["Distance km", (t) => t.distance_km, (t) => t.distance_km],
        ["Sprints", (t) => t.sprints, (t) => t.sprints],
      ])}</div>`;
      fp.innerHTML = flowHtml(true);
    } else if (mode === "casual") {
      const mom = snap.momentum_home, top = mom >= 0.58 ? S.match.home : mom <= 0.42 ? S.match.away : null;
      const label = { control: "Calm and patient", chaos: "End to end and wild", contested: "Evenly matched" }[snap.control.label];
      sp.innerHTML = `<h2>The story so far <small>${snap.minute}</small></h2><p class="plain">${top ? `<strong style="color:${top.color}">${esc(top.short)}</strong> are on top right now.` : `<strong>Nobody</strong> is in charge right now.`} The game feels <strong>${label.toLowerCase()}</strong>.</p>`;
      fp.innerHTML = `<h2>Quick numbers</h2>${head}<div class="cmp">${rows([
        ["Possession %", (t, s) => s.possession[S.match.home.code], (t, s) => s.possession[S.match.away.code]],
        ["Shots", (t) => t.shots, (t) => t.shots],
        ["On target", (t) => t.on_target, (t) => t.on_target],
      ])}</div>`;
    } else {
      const pid = S.profile.player, p = player(pid), ps = (snap.players || {})[pid] || {};
      const color = p && p.team === S.match.home.code ? S.match.home.color : S.match.away.color;
      sp.innerHTML = p ? `<h2>Player focus <small>${snap.minute}</small></h2><div class="pcard"><div class="who"><span class="num" style="background:${color}">${p.number}</span><span><span class="name">${esc(p.name)}</span><br><span class="meta">${esc(p.role)} · ${p.team === S.match.home.code ? esc(S.match.home.name) : esc(S.match.away.name)}${ps.on_pitch === false ? " · off the pitch" : ""}</span></span></div>
        <div class="kv"><div><b>${(ps.distance_km ?? 0).toFixed(1)}</b><span>km run</span></div><div><b>${ps.top_speed || "-"}</b><span>top km/h</span></div><div><b>${ps.sprints ?? 0}</b><span>sprints</span></div>
        <div><b>${ps.passes_completed ?? 0}/${ps.passes ?? 0}</b><span>passes</span></div><div><b>${ps.pressures ?? 0}</b><span>pressures</span></div><div><b>${ps.shots ?? 0}</b><span>shots</span></div>
        <div><b>${(ps.xg ?? 0).toFixed(2)}</b><span>xG</span></div><div><b>${(ps.tackles ?? 0) + (ps.interceptions ?? 0)}</b><span>tackles + int.</span></div><div><b>${ps.goals ?? 0}</b><span>goals</span></div></div></div>` : "";
      fp.innerHTML = flowHtml(false);
    }
  }
  function flowHtml(detail) {
    const snap = S.snapshot, c = snap.control;
    const pts = S.series.filter((p) => p.t <= (STATIC ? S.t : Infinity)).slice(-45);
    const W = 300, H = 70;
    let spark = "";
    if (pts.length > 1) {
      const xs = (i) => (i / (pts.length - 1)) * W, ys = (v) => H - v * H;
      const line = pts.map((p, i) => `${xs(i).toFixed(1)},${ys(p.momentum_home).toFixed(1)}`).join(" ");
      spark = `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Momentum, home share of threat">
        <defs><clipPath id="ab"><rect x="0" y="0" width="${W}" height="${H / 2}"/></clipPath><clipPath id="be"><rect x="0" y="${H / 2}" width="${W}" height="${H / 2}"/></clipPath></defs>
        <polygon points="0,${H / 2} ${line} ${W},${H / 2}" fill="${S.match.home.color}" opacity=".45" clip-path="url(#ab)"/>
        <polygon points="0,${H / 2} ${line} ${W},${H / 2}" fill="${S.match.away.color}" opacity=".45" clip-path="url(#be)"/>
        <line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" stroke="currentColor" stroke-opacity=".25" stroke-dasharray="3 3"/>
        <polyline points="${line}" fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
    }
    const pos = ((c.index + 1) / 2) * 100;
    return `<h2>Flow of the game <small>last ${pts.length} min</small></h2>
      <div class="meta" style="display:flex;justify-content:space-between"><span style="color:${S.match.home.color}">${esc(S.match.home.short)} threat</span><span style="color:${S.match.away.color}">${esc(S.match.away.short)} threat</span></div>
      ${spark || '<div class="empty">Building the momentum line…</div>'}
      <div class="gauge" style="margin-top:12px"><div style="display:flex;justify-content:space-between;align-items:baseline"><span class="now">${c.label}</span><span class="meta">index ${c.index.toFixed(2)}</span></div>
      <div class="track"><span class="knob" style="left:${pos}%"></span></div><div class="ends"><span>Chaos</span><span>Control</span></div>
      ${detail ? `<div class="meta">${c.switches_per_min} possession changes/min · ${c.avg_chain} passes per move · ${c.long_ball_pct}% long balls (last 10 min)</div>` : ""}</div>`;
  }

  function renderMoments() {
    const list = S.aired.filter(wantsRec).slice().reverse();
    $("momCount").textContent = `${list.length} aired`;
    if (!list.length) { $("moments").innerHTML = `<div class="empty">Overlays appear here as the director puts them to air.</div>`; return; }
    $("moments").innerHTML = list.map((r, i) => {
      const color = r.team ? (r.team === S.match.home.code ? S.match.home.color : S.match.away.color) : "var(--accent)";
      return `<button type="button" class="mom" data-i="${i}"><span class="m">${esc(r.minute)}</span><span><span class="h"><i style="background:${color}"></i>${esc(r.headline)}</span><span class="b">${esc(r.body)}</span></span></button>`;
    }).join("");
    $("moments").querySelectorAll(".mom").forEach((b) => b.addEventListener("click", () => openDrawer(list[Number(b.dataset.i)])));
  }

  // ------------------------------------------------------------------ why drawer
  function openDrawer(rec) {
    const d = $("drawer");
    const ev = rec.evidence || {};
    const items = Object.entries(ev).filter(([k, v]) => v !== null && typeof v !== "object" || k === "why_tags");
    const fmtV = (v) => Array.isArray(v) ? v.join(", ").replace(/_/g, " ") : typeof v === "boolean" ? (v ? "yes" : "no") : v;
    const src = rec.source === "foundry" ? '<span class="badge ai">Foundry agent</span>' : rec.source === "producer" ? '<span class="badge">Producer edit</span>' : '<span class="badge">Template</span>';
    const ver = (rec.verifier || []).length ? `<span class="badge no">Verifier fell back: ${esc(rec.verifier[0])}</span>` : '<span class="badge ok">Verified against evidence</span>';
    const ctx = rec.context || {};
    d.innerHTML = `<button class="btn close" type="button" id="closeDrawer">Close</button>
      <div class="sec">${esc(rec.minute)} · ${esc((LABELS[rec.type] || {}).en || rec.type)}</div>
      <h3>${esc(rec.headline)}</h3>
      <div class="why">${esc(rec.why || rec.body)}</div>
      <div class="chips">${src}${ver}<span class="badge">${esc(rec.slot.replace("_", " "))}</span>${rec.latency_ms != null ? `<span class="badge">${rec.latency_ms} ms</span>` : ""}</div>
      <div class="sec">Evidence from the stats engine</div>
      <dl>${items.map(([k, v]) => `<dt>${esc(EV_LABELS[k] || k.replace(/_/g, " "))}</dt><dd>${esc(String(fmtV(v)))}</dd>`).join("")}</dl>
      <div class="sec">Match context at the moment</div>
      <dl><dt>Score</dt><dd>${ctx.score ? Object.values(ctx.score).join("-") : "-"}</dd><dt>Home threat share</dt><dd>${ctx.momentum_home != null ? Math.round(ctx.momentum_home * 100) + "%" : "-"}</dd><dt>Rhythm</dt><dd>${esc(ctx.control_label || "-")} (${ctx.control_index ?? "-"})</dd></dl>
      <details><summary>Overlay JSON sent to the renderer</summary><pre>${esc(JSON.stringify({ ...rec, evidence: undefined, context: undefined }, null, 2))}</pre></details>`;
    d.hidden = false;
    $("closeDrawer").addEventListener("click", () => { d.hidden = true; });
    $("closeDrawer").focus();
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("drawer").hidden = true; });

  // ------------------------------------------------------------------ controls
  $("modeSeg").addEventListener("click", (e) => { const v = e.target.closest("button")?.dataset.v; if (v) setProfile({ mode: v }); });
  $("langSeg").addEventListener("click", (e) => { const v = e.target.closest("button")?.dataset.v; if (v) setProfile({ lang: v }); });
  $("clubSel").addEventListener("change", (e) => setProfile({ club: e.target.value }));
  $("playerSel").addEventListener("change", (e) => setProfile({ player: e.target.value }));
  $("speedSeg").addEventListener("click", (e) => {
    const v = Number(e.target.closest("button")?.dataset.v); if (!v) return;
    S.speed = v; syncControls();
    if (!STATIC) control({ action: "speed", speed: v });
  });
  $("playBtn").addEventListener("click", () => {
    S.playing = !S.playing;
    $("playBtn").textContent = S.playing ? "Pause" : "Play";
    if (STATIC && S.playing && S.t >= TL.final.t) seek(0);
    if (!STATIC) control({ action: S.playing ? "resume" : "pause" });
    setLive();
  });
  function setLive() {
    const paused = !S.playing || S.state === "paused" || S.state === "finished";
    $("liveDot").classList.toggle("paused", paused);
    $("liveLbl").textContent = S.state === "finished" ? "Full-time" : paused ? "Paused" : STATIC ? `Replay ${S.speed}×` : `Live ${S.speed}×`;
  }

  // ------------------------------------------------------------------ static source
  let ei = 0, si = 0, mi = 0;
  function seek(t) {
    S.t = t;
    clearSlots();
    pitch.setMatch(S.match);
    pitch.focus = S.profile.mode === "player" ? S.profile.player : null;
    ei = 0; si = 0; mi = 0;
    while (ei < TL.events.length && TL.events[ei].t <= t) { onEvent(TL.events[ei], true); ei++; }
    pitch.snap();
    while (si < TL.snapshots.length && TL.snapshots[si].t <= t) si++;
    S.snapshot = si > 0 ? TL.snapshots[si - 1] : null;
    while (mi < TL.moments.length && TL.moments[mi].t <= t) mi++;
    S.aired = TL.moments.slice(0, mi).map(staticRecord);
    if (S.snapshot) { setScore(S.snapshot.score); $("clock").textContent = S.snapshot.clock; } else { setScore({ [S.match.home.code]: 0, [S.match.away.code]: 0 }); $("clock").textContent = "00:00"; }
    S.state = t >= TL.final.t ? "finished" : "live";
    renderRail(); renderMoments(); setLive();
  }
  function startStatic() {
    setMatch(TL.match);
    S.series = TL.series;
    $("srcTag").textContent = "Synthetic match · replay";
    if ($("deskLink")) $("deskLink").hidden = true;
    $("agentInfo").textContent = "Overlays: deterministic template agents (EN, HI, TA), each checked by the verifier.";
    const scrub = $("scrub");
    scrub.max = String(Math.ceil(TL.final.t));
    scrub.addEventListener("input", () => seek(Number(scrub.value)));
    const goals = TL.moments.filter((m) => ["goal", "half_time", "press_shift"].includes(m.type) && (m.type !== "press_shift" || m.evidence.direction === "fading"));
    $("jumps").innerHTML = goals.map((m) => `<button type="button" class="btn" data-t="${m.t - 25}">${esc(m.minute)} ${m.type === "goal" ? esc(m.evidence.scorer.split(" ").pop()) : m.type === "half_time" ? "HT" : "Press fades"}</button>`).join("");
    $("jumps").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { seek(Math.max(0, Number(b.dataset.t))); S.playing = true; $("playBtn").textContent = "Pause"; setLive(); } });
    seek(0);
    let last = performance.now();
    const loop = (now) => {
      const dt = Math.min(0.25, (now - last) / 1000); last = now;
      if (S.playing && S.t < TL.final.t) {
        S.t += dt * S.speed;
        while (ei < TL.events.length && TL.events[ei].t <= S.t) { onEvent(TL.events[ei], false); ei++; }
        let statsChanged = false;
        while (si < TL.snapshots.length && TL.snapshots[si].t <= S.t) { S.snapshot = TL.snapshots[si]; si++; statsChanged = true; }
        if (statsChanged) { setScore(S.snapshot.score); renderRail(); }
        while (mi < TL.moments.length && TL.moments[mi].t <= S.t) {
          const m = TL.moments[mi++];
          const rec = staticRecord(m);
          S.aired.push(rec);
          if (wants(m)) show(rec);
          renderMoments();
        }
        scrub.value = String(Math.round(S.t));
        if (S.t >= TL.final.t) { S.state = "finished"; S.playing = false; $("playBtn").textContent = "Replay"; setLive(); }
      }
      tickSlots(now);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  // ------------------------------------------------------------------ live source
  let ws = null;
  function send(msg) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg)); }
  async function control(body) {
    try { await fetch("/api/control", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); } catch (e) { /* offline */ }
  }
  async function refreshLiveHistory() {
    const q = new URLSearchParams({ mode: S.profile.mode, lang: S.profile.lang, club: S.profile.club || "", player: S.profile.player || "" });
    try {
      const r = await fetch(`/api/overlays?${q}`);
      const j = await r.json();
      S.aired = j.overlays; renderMoments();
    } catch (e) { /* keep current list */ }
  }
  function startLive() {
    $("scrubWrap").hidden = true;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/viewer`);
    ws.onopen = () => send({ type: "profile", profile: S.profile });
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "hello") {
        setMatch(msg.match); S.speed = msg.speed; S.state = msg.state; S.agents = msg.agents;
        $("agentInfo").textContent = msg.agents.startsWith("foundry") ? `Agents: Microsoft Foundry (${msg.agents.split(":")[1]}) with verifier and template fallback.` : "Agents: template mode (set FOUNDRY_PROJECT_ENDPOINT to enable Foundry).";
        (msg.recent_events || []).forEach((ev) => onEvent(ev, true)); pitch.snap();
        if (msg.snapshot) onStats(msg.snapshot);
        refreshLiveHistory(); syncControls(); setLive();
      } else if (msg.type === "event") onEvent(msg.event, false);
      else if (msg.type === "stats") onStats(msg.stats);
      else if (msg.type === "overlay") {
        if (msg.overlay.replay) { const i = S.aired.findIndex((r) => r.moment_id === msg.overlay.moment_id); if (i >= 0) S.aired[i] = msg.overlay; mount(msg.overlay); renderMoments(); }
        else onOverlay(msg.overlay);
      } else if (msg.type === "state") { S.state = msg.state; S.speed = msg.speed; S.playing = msg.state !== "paused"; $("playBtn").textContent = S.playing ? "Pause" : "Play"; syncControls(); setLive(); }
      else if (msg.type === "reset") { S.aired = []; clearSlots(); setMatch(msg.match); S.snapshot = null; setScore({ [msg.match.home.code]: 0, [msg.match.away.code]: 0 }); renderRail(); renderMoments(); }
    };
    ws.onclose = () => { $("liveLbl").textContent = "Reconnecting"; setTimeout(startLive, 2000); };
    if (!startLive.looping) {
      startLive.looping = true;
      const loop = (now) => { tickSlots(now); requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    }
  }

  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  if (STATIC) startStatic(); else startLive();
})();
