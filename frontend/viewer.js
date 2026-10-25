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
      verifier: [], graphic, evidence: m.evidence, context: m.context, analysis: m.analysis };
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
    const teamColor = rec.team ? (rec.team === S.match.home.code ? S.match.home.color : S.match.away.color) : "var(--ink)";
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
      sp.innerHTML = p ? `<h2>Player focus <small>${snap.minute}</small></h2><div class="pcard"><div class="who"><span class="num" style="border-color:${color}">${p.number}</span><span><span class="name">${esc(p.name)}</span><br><span class="meta">${esc(p.role)} · ${p.team === S.match.home.code ? esc(S.match.home.name) : esc(S.match.away.name)}${ps.on_pitch === false ? " · off the pitch" : ""}</span></span></div>
        <div class="kv"><div><b>${(ps.distance_km ?? 0).toFixed(1)}</b><span>km run</span></div><div><b>${ps.top_speed || "-"}</b><span>top km/h</span></div><div><b>${ps.sprints ?? 0}</b><span>sprints</span></div>
        <div><b>${ps.passes_completed ?? 0}/${ps.passes ?? 0}</b><span>passes</span></div><div><b>${ps.pressures ?? 0}</b><span>pressures</span></div><div><b>${ps.shots ?? 0}</b><span>shots</span></div>
        <div><b>${(ps.xg ?? 0).toFixed(2)}</b><span>xG</span></div><div><b>${(ps.tackles ?? 0) + (ps.interceptions ?? 0)}</b><span>tackles + int.</span></div><div><b>${ps.goals ?? 0}</b><span>goals</span></div></div></div>` : "";
      fp.innerHTML = flowHtml(false);
    }
    if (S.an.tab === "all") renderAnalysis();
  }
  function flowHtml(detail) {
    const snap = S.snapshot, c = snap.control;
    const pts = S.series.filter((p) => p.t <= (STATIC ? S.t : Infinity)).slice(-45);
    const W = 300, H = 86;
    let spark = "";
    if (pts.length > 1) {
      const xs = (i) => (i / (pts.length - 1)) * W, ys = (v) => 4 + (1 - v) * (H - 8);
      const line = pts.map((p, i) => `${xs(i).toFixed(1)},${ys(p.momentum_home).toFixed(1)}`).join(" ");
      const mid = ys(0.5);
      let grid = "";
      pts.forEach((p, i) => { if (i % 10 === 0) grid += `<line x1="${xs(i).toFixed(1)}" x2="${xs(i).toFixed(1)}" y1="0" y2="${H}" stroke="currentColor" stroke-opacity=".08" vector-effect="non-scaling-stroke"/>`; });
      spark = `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Momentum, home share of threat">
        <defs><clipPath id="ab"><rect x="0" y="0" width="${W}" height="${mid}"/></clipPath><clipPath id="be"><rect x="0" y="${mid}" width="${W}" height="${H - mid}"/></clipPath></defs>
        ${grid}
        <polygon points="0,${mid} ${line} ${W},${mid}" fill="${S.match.home.color}" opacity=".16" clip-path="url(#ab)"/>
        <polygon points="0,${mid} ${line} ${W},${mid}" fill="${S.match.away.color}" opacity=".16" clip-path="url(#be)"/>
        <line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="currentColor" stroke-opacity=".22" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/>
        <polyline points="${line}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>`;
    }
    const pos = ((c.index + 1) / 2) * 100;
    return `<h2>Flow of the game <small>last ${pts.length} min</small></h2>
      <div class="meta" style="display:flex;justify-content:space-between"><span style="color:${S.match.home.color}">${esc(S.match.home.short)} threat</span><span style="color:${S.match.away.color}">${esc(S.match.away.short)} threat</span></div>
      ${spark || '<div class="empty">Building the momentum line…</div>'}
      <div class="gauge" style="margin-top:16px"><div style="display:flex;justify-content:space-between;align-items:baseline"><span class="now">${c.label}</span><span class="meta">index ${c.index.toFixed(2)}</span></div>
      <div class="track"><span class="knob" style="left:${pos}%"></span></div><div class="ends"><span>Chaos</span><span>Control</span></div>
      ${detail ? `<div class="meta">${c.switches_per_min} possession changes/min · ${c.avg_chain} passes per move · ${c.long_ball_pct}% long balls (last 10 min)</div>` : ""}</div>`;
  }

  function renderMoments() {
    const list = S.aired.filter(wantsRec).slice().reverse();
    $("momCount").textContent = `${list.length} aired`;
    if (!list.length) { $("moments").innerHTML = `<div class="empty">Overlays land here as the director puts them to air.</div>`; renderAnalysis(); return; }
    $("moments").innerHTML = list.map((r, i) => {
      const color = r.team ? (r.team === S.match.home.code ? S.match.home.color : S.match.away.color) : "var(--ink)";
      return `<button type="button" class="mom" data-i="${i}"><span class="m">${esc(r.minute)}</span><span><span class="h"><i style="background:${color}"></i>${esc(r.headline)}</span><span class="b">${esc(r.body)}</span></span></button>`;
    }).join("");
    $("moments").querySelectorAll(".mom").forEach((b) => b.addEventListener("click", () => openDrawer(list[Number(b.dataset.i)])));
    renderAnalysis();
  }

  // ------------------------------------------------------------------ goal analysis
  // The build-up behind a goal or big chance, read from the event stream by the stats engine
  // (backend/app/buildup.py). Sentences arrive pre-written and verified in every language.
  const PATTERN = {
    counter_attack: { en: "Counterattack", hi: "काउंटर-अटैक", ta: "எதிர்த்தாக்குதல்" },
    high_regain: { en: "High regain", hi: "ऊँचे पर गेंद जीती", ta: "மேலே பந்து மீட்பு" },
    short_passing: { en: "Short passing sequence", hi: "छोटे पासों की कड़ी", ta: "குறும் பாஸ் தொடர்" },
    set_piece: { en: "Set piece", hi: "सेट पीस", ta: "செட் பீஸ்" },
    box_entry: { en: "Into the penalty area", hi: "पेनल्टी एरिया में प्रवेश", ta: "பெனால்டி பகுதிக்குள்" },
    half_space: { en: "Half-space attack", hi: "हाफ़-स्पेस से हमला", ta: "ஹாஃப்-ஸ்பேஸ் தாக்குதல்" },
    third_man: { en: "Third-man run", hi: "थर्ड-मैन रन", ta: "மூன்றாம் வீரர் ஓட்டம்" },
    one_two: { en: "One-two", hi: "वन-टू", ta: "ஒன்-டூ" },
    switch_play: { en: "Switch of play", hi: "खेल की दिशा बदली", ta: "ஆட்டத் திசை மாற்றம்" },
    line_break: { en: "Line-breaking pass", hi: "लाइन तोड़ता पास", ta: "வரிசை உடைக்கும் பாஸ்" },
    second_ball: { en: "Second ball", hi: "सेकंड बॉल", ta: "இரண்டாம் பந்து" },
    overload: { en: "Numerical overload", hi: "संख्या में बढ़त", ta: "எண்ணிக்கை மேலாதிக்கம்" },
    time_space: { en: "Time and space", hi: "समय और जगह", ta: "நேரமும் இடமும்" },
  };
  const UI = {
    en: { goal: "Goal", chance: "Big chance", passes: "passes", seconds: "seconds", players: "players on the ball", metres: "metres gained",
      entries: "box entries", frame: "Freeze frame", move: "The move", pass: "Pass", carry: "Carry", run: "Run", shot: "Shot", won: "Won here",
      frameNote: (t) => `Freeze frame ${Math.abs(t)}s before the shot. Players on the ball are where the data puts them; everyone else is estimated from the team shape.`,
      moveNote: "Numbers are shirt numbers, in the order the move happened.",
      origin: { regain: (o, how) => `Won back by <b>${o}</b> with ${how}`, corner: () => "Started from a <b>corner</b>", free_kick: () => "Started from a <b>free kick</b>",
        kickoff: () => "Started from the <b>kick-off</b>", goalkeeper: (o) => `Started by the goalkeeper, <b>${o}</b>`, open_play: (o) => `Open play, started by <b>${o}</b>` },
      how: { tackle: "a tackle", interception: "an interception", ball_recovery: "a loose ball", counterpress: "a counter-press" },
      fromGoal: (m) => `${m} m from goal`, finish: (f) => `${f.xg} xG · ${f.speed_kmh} km/h from ${f.distance_m} m`,
      allNote: "Every shot so far, grouped by what created it. A shot can show more than one pattern.", shots: "Shots", goals: "Goals",
      setp: "Set pieces", openp: "Open play", empty: "No goals or big chances yet. The first one will be broken down here." },
    hi: { goal: "गोल", chance: "बड़ा मौका", passes: "पास", seconds: "सेकंड", players: "खिलाड़ी शामिल", metres: "मीटर आगे", entries: "बॉक्स प्रवेश",
      frame: "फ़्रीज़ फ़्रेम", move: "पूरी मूव", pass: "पास", carry: "कैरी", run: "रन", shot: "शॉट", won: "यहाँ जीती",
      frameNote: (t) => `शॉट से ${Math.abs(t)} सेकंड पहले का फ़्रीज़ फ़्रेम। गेंद वाले खिलाड़ी डेटा के मुताबिक़; बाक़ी टीम शेप से अनुमानित।`,
      moveNote: "नंबर जर्सी नंबर हैं, मूव के क्रम में।",
      origin: { regain: (o, how) => `<b>${o}</b> ने ${how} से गेंद जीती`, corner: () => "<b>कॉर्नर</b> से शुरुआत", free_kick: () => "<b>फ़्री-किक</b> से शुरुआत",
        kickoff: () => "<b>किक-ऑफ़</b> से शुरुआत", goalkeeper: (o) => `गोलकीपर <b>${o}</b> से शुरुआत`, open_play: (o) => `ओपन प्ले, <b>${o}</b> से शुरुआत` },
      how: { tackle: "टैकल", interception: "इंटरसेप्शन", ball_recovery: "ढीली गेंद उठाकर", counterpress: "काउंटर-प्रेस" },
      fromGoal: (m) => `गोल से ${m} मीटर`, finish: (f) => `${f.xg} xG · ${f.distance_m} मीटर से ${f.speed_kmh} km/h`,
      allNote: "अब तक के सभी शॉट, जिस पैटर्न से बने। एक शॉट में कई पैटर्न हो सकते हैं।", shots: "शॉट", goals: "गोल",
      setp: "सेट पीस", openp: "ओपन प्ले", empty: "अभी कोई गोल या बड़ा मौका नहीं। पहला यहाँ समझाया जाएगा।" },
    ta: { goal: "கோல்", chance: "பெரிய வாய்ப்பு", passes: "பாஸ்கள்", seconds: "வினாடிகள்", players: "வீரர்கள் பங்கேற்பு", metres: "மீ முன்னேற்றம்", entries: "பெட்டி நுழைவு",
      frame: "உறைநிலை படம்", move: "முழு நகர்வு", pass: "பாஸ்", carry: "கேரி", run: "ஓட்டம்", shot: "ஷாட்", won: "இங்கே மீட்பு",
      frameNote: (t) => `ஷாட்டுக்கு ${Math.abs(t)} வினாடி முன் உறைநிலை படம். பந்துடன் உள்ள வீரர்கள் தரவின்படி; மற்றவர்கள் அணி அமைப்பிலிருந்து மதிப்பீடு.`,
      moveNote: "எண்கள் ஜெர்சி எண்கள், நகர்வின் வரிசையில்.",
      origin: { regain: (o, how) => `<b>${o}</b> ${how} மூலம் பந்தை மீட்டார்`, corner: () => "<b>கார்னர்</b> மூலம் தொடக்கம்", free_kick: () => "<b>ஃப்ரீ கிக்</b> மூலம் தொடக்கம்",
        kickoff: () => "<b>கிக்-ஆஃப்</b> மூலம் தொடக்கம்", goalkeeper: (o) => `கோல்கீப்பர் <b>${o}</b> தொடங்கினார்`, open_play: (o) => `திறந்த ஆட்டம், <b>${o}</b> தொடங்கினார்` },
      how: { tackle: "டேக்கிள்", interception: "இடைமறிப்பு", ball_recovery: "தளர்ந்த பந்து", counterpress: "கவுண்டர்-பிரஸ்" },
      fromGoal: (m) => `கோலிலிருந்து ${m} மீ`, finish: (f) => `${f.xg} xG · ${f.distance_m} மீ தூரத்திலிருந்து ${f.speed_kmh} km/h`,
      allNote: "இதுவரை எல்லா ஷாட்களும், அவற்றை உருவாக்கிய முறைப்படி. ஒரு ஷாட்டில் பல முறைகள் இருக்கலாம்.", shots: "ஷாட்கள்", goals: "கோல்கள்",
      setp: "செட் பீஸ்", openp: "திறந்த ஆட்டம்", empty: "இன்னும் கோல் அல்லது பெரிய வாய்ப்பு இல்லை. முதலாவது இங்கே விளக்கப்படும்." },
  };
  S.an = { id: null, tab: "one", frame: false, pin: null, auto: true };

  function teamColor(code) { return code === S.match.home.code ? S.match.home.color : S.match.away.color; }
  function otherColor(code) { return code === S.match.home.code ? S.match.away.color : S.match.home.color; }
  function analysisCandidates() { return S.aired.filter((r) => r.analysis); }

  function pitchLines() {
    let st = "";
    for (let i = 0; i < 14; i += 2) st += `<rect x="${i * 7.5}" y="0" width="7.5" height="68" fill="var(--pitch-2)"/>`;
    return `<rect x="-3" y="-3" width="111" height="74" rx="3" fill="var(--pitch)"/>${st}
      <g fill="none" stroke="var(--pitch-line)" stroke-width=".35">
        <rect x="0" y="0" width="105" height="68"/><line x1="52.5" y1="0" x2="52.5" y2="68"/><circle cx="52.5" cy="34" r="9.15"/>
        <rect x="0" y="13.84" width="16.5" height="40.32"/><rect x="88.5" y="13.84" width="16.5" height="40.32"/>
        <rect x="0" y="24.84" width="5.5" height="18.32"/><rect x="99.5" y="24.84" width="5.5" height="18.32"/>
        <path d="M16.5 26.7 A9.15 9.15 0 0 1 16.5 41.3"/><path d="M88.5 26.7 A9.15 9.15 0 0 0 88.5 41.3"/>
        <rect x="-1.6" y="30.34" width="1.6" height="7.32"/><rect x="105" y="30.34" width="1.6" height="7.32"/>
      </g>`;
  }
  function disc(x, y, num, ring, opts = {}) {
    const r = opts.r || 2.4;
    return `<g class="${opts.cls || ""}" ${opts.k != null ? `data-k="${opts.k}"` : ""} opacity="${opts.op ?? 1}">
      <circle cx="${x}" cy="${y + 0.3}" r="${r}" fill="rgba(20,30,20,.16)"/>
      <circle cx="${x}" cy="${y}" r="${r}" fill="${opts.fill || "var(--player-fill)"}" stroke="${ring}" stroke-width="${opts.sw || 0.6}"/>
      <text x="${x}" y="${y + 0.75}" text-anchor="middle" font-size="${r * 1.02}" font-weight="700" fill="${opts.ink || "var(--player-ink)"}" font-family="Figtree, system-ui, sans-serif">${num}</text></g>`;
  }
  function tagLabel(x, y, text) {
    const w = Math.max(6, text.length * 1.05 + 2.4);
    return `<g><rect x="${x - w / 2}" y="${y - 1.7}" width="${w}" height="3.4" rx="1.7" fill="var(--ink)"/>
      <text x="${x}" y="${y + 0.75}" text-anchor="middle" font-size="2" font-weight="600" fill="var(--ink-fg)" font-family="Figtree, system-ui, sans-serif">${esc(text)}</text></g>`;
  }
  function moveSvg(a) {
    const col = teamColor(a.team), ui = UI[S.profile.lang];
    const steps = a.steps, n = steps.length;
    let lines = "", discs = "", labels = "";
    const num = (pid) => (player(pid) || {}).number || "";
    steps.forEach((s, k) => {
      const age = n > 1 ? k / (n - 1) : 1, op = (0.45 + 0.55 * age).toFixed(2);
      if (s.type === "pass") lines += `<line class="st" data-k="${k}" x1="${s.x}" y1="${s.y}" x2="${s.ex}" y2="${s.ey}" stroke="var(--ink)" stroke-width=".55" marker-end="url(#ah)" opacity="${op}"/>`;
      else if (s.type === "carry" || s.type === "dribble") lines += `<line class="st" data-k="${k}" x1="${s.x}" y1="${s.y}" x2="${s.ex}" y2="${s.ey}" stroke="var(--ink)" stroke-width=".5" stroke-dasharray="1.4 1" opacity="${op}"/>`;
      else if (s.type === "sprint") lines += `<line class="st" data-k="${k}" x1="${s.x}" y1="${s.y}" x2="${s.ex}" y2="${s.ey}" stroke="${col}" stroke-width=".5" stroke-dasharray=".2 1.1" stroke-linecap="round" opacity=".9"/>`;
      else if (s.type === "shot") lines += `<line class="st" data-k="${k}" x1="${s.x}" y1="${s.y}" x2="105" y2="${s.ey}" stroke="${col}" stroke-width=".9" marker-end="url(#ahc)"/>`;
      if (s.type !== "sprint") discs += disc(s.x, s.y, num(s.player), col, { k, op, cls: "st-d" });
    });
    const shot = steps[n - 1], o = a.origin;
    if (o.type === "regain" && o.x != null) {
      discs = `<g transform="translate(${o.x} ${o.y}) rotate(45)"><rect x="-1.5" y="-1.5" width="3" height="3" fill="var(--ink)"/></g>` + discs;
      labels += tagLabel(o.x, Math.max(3, o.y - 4.2), ui.won);
    }
    if (shot) labels += tagLabel(shot.x, Math.min(65, shot.y + 4.4), (player(shot.player) || {}).short || "");
    return `${lines}${discs}${labels}`;
  }
  function frameSvg(a) {
    const f = a.frame, col = teamColor(a.team), opp = otherColor(a.team);
    if (!f) return "";
    let out = `<circle cx="${f.ball[0]}" cy="${f.ball[1]}" r="${f.radius}" fill="${col}" fill-opacity=".09" stroke="var(--ink)" stroke-width=".35" stroke-dasharray="1.2 1"/>`;
    for (const [pid, x, y, att] of f.players) out += disc(x, y, (player(pid) || {}).number || "", att ? col : opp, att ? { r: 1.9 } : { r: 1.9, fill: opp, ink: "#fff", sw: 0.3 });
    out += `<circle cx="${f.ball[0]}" cy="${f.ball[1]}" r=".9" fill="#fff" stroke="var(--ink)" stroke-width=".3"/>`;
    const lx = Math.min(98, Math.max(7, f.ball[0])), ly = Math.max(4, f.ball[1] - f.radius - 1.5);
    out += tagLabel(lx, ly, `${f.attackers} v ${f.defenders}`);
    return out;
  }
  function analysisSvg(a) {
    const col = teamColor(a.team);
    // Crop to the part of the pitch the move used, so short moves are not lost in empty grass.
    const xs = a.steps.map((s) => Math.min(s.x, s.ex)).concat(a.origin.x != null ? [a.origin.x] : []);
    const x0 = S.an.frame ? -3 : Math.max(-3, Math.min(40, Math.min(...xs) - 7));
    return `<svg viewBox="${x0} -3 ${108 - x0} 74" role="img" aria-label="Diagram of the move">
      <defs><marker id="ah" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="var(--ink)"/></marker>
      <marker id="ahc" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3" markerHeight="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="${col}"/></marker></defs>
      ${pitchLines()}<g id="anLayer">${S.an.frame ? frameSvg(a) : moveSvg(a)}</g></svg>`;
  }
  function timelineHtml(a) {
    const T = Math.max(1, -a.steps[0].t, a.summary.seconds);
    const dots = a.steps.filter((s) => s.type !== "sprint").map((s) => {
      const k = a.steps.indexOf(s);
      return `<span class="dot ${s.type === "shot" ? "shot" : ""}" data-k="${k}" style="left:${(100 * (T + s.t)) / T}%" title="${esc(((player(s.player) || {}).short || "") + " · " + s.type)}"></span>`;
    }).join("");
    return `<div class="an-time" aria-hidden="true"><span class="axis"></span>${dots}<span class="lab" style="left:0;transform:none">−${Math.round(T)}s</span><span class="lab" style="left:auto;right:0;transform:none">0s</span></div>`;
  }
  function highlight(steps) {
    const set = new Set(steps || []);
    document.querySelectorAll("#anBody [data-k]").forEach((el) => {
      const on = set.has(Number(el.dataset.k));
      if (el.tagName === "line") {
        if (el.dataset.w == null) el.dataset.w = el.getAttribute("stroke-width");
        el.setAttribute("stroke-width", on ? "1.1" : el.dataset.w);
        el.style.stroke = on ? "var(--mint-ink)" : "";
      } else el.classList.toggle("hl", on);
    });
  }
  function renderAnalysis() {
    if (!S.match) return;
    const body = $("anBody"), ui = UI[S.profile.lang], lang = S.profile.lang;
    for (const b of $("anTabs").children) b.setAttribute("aria-pressed", String(b.dataset.v === S.an.tab));
    if (S.an.tab === "all") { body.innerHTML = chancesHtml(); return; }
    const list = analysisCandidates();
    if (!list.length) { body.innerHTML = `<div class="empty">${ui.empty}</div>`; return; }
    let rec = list.find((r) => r.moment_id === S.an.id);
    if (!rec || S.an.auto) { rec = [...list].reverse().find((r) => r.type === "goal") || list[list.length - 1]; S.an.id = rec.moment_id; }
    const a = rec.analysis, f = a.finish, col = teamColor(a.team), p = player(f.player) || {};
    const copy = (a.copy && (a.copy[lang] || a.copy.en)) || [];
    const o = a.origin, howT = ui.how[o.how] || ui.how.tackle;
    let origin = (ui.origin[o.type] || ui.origin.open_play)(esc(o.player_name || ""), howT);
    if (o.type === "regain" && o.x != null) origin += ` · ${ui.fromGoal(Math.round(105 - o.x))}`;
    const sm = a.summary;
    body.innerHTML = `
      <div class="an-pick">${list.map((r) => `<button type="button" class="btn" data-id="${r.moment_id}" aria-pressed="${r.moment_id === rec.moment_id}"><i style="background:${teamColor(r.team)}"></i>${esc(r.minute)} ${esc(((player((r.analysis.finish || {}).player) || {}).short) || "")}${r.type === "goal" ? "" : " · " + esc(ui.chance)}</button>`).join("")}</div>
      <div class="an-grid">
        <div>
          <div class="an-hero"><span class="num" style="border-color:${col}">${p.number || ""}</span><span><span class="t">${esc(p.name || "")} · ${esc(rec.minute)}</span><br><span class="s">${esc(rec.type === "goal" ? ui.goal : ui.chance)} · ${esc(ui.finish(f))}</span></span></div>
          <div class="an-pitch">${analysisSvg(a)}</div>
          <div class="an-tools">
            <div class="an-legend">
              <span><svg viewBox="0 0 22 8"><line x1="1" y1="4" x2="21" y2="4" stroke="currentColor" stroke-width="1.6"/></svg>${ui.pass}</span>
              <span><svg viewBox="0 0 22 8"><line x1="1" y1="4" x2="21" y2="4" stroke="currentColor" stroke-width="1.6" stroke-dasharray="4 3"/></svg>${ui.carry}</span>
              <span><svg viewBox="0 0 22 8"><line x1="1" y1="4" x2="21" y2="4" stroke="${col}" stroke-width="2" stroke-dasharray=".5 3.5" stroke-linecap="round"/></svg>${ui.run}</span>
              <span><svg viewBox="0 0 22 8"><line x1="1" y1="4" x2="21" y2="4" stroke="${col}" stroke-width="2.4"/></svg>${ui.shot}</span>
            </div>
            <div class="seg small" id="anView"><button type="button" data-v="move" aria-pressed="${!S.an.frame}">${ui.move}</button><button type="button" data-v="frame" aria-pressed="${S.an.frame}">${ui.frame}</button></div>
          </div>
          ${S.an.frame ? "" : timelineHtml(a)}
          <div class="an-note">${S.an.frame && a.frame ? esc(ui.frameNote(a.frame.t)) : esc(ui.moveNote)}</div>
        </div>
        <div>
          <div class="an-stats">
            <div><b>${sm.passes}</b><span>${ui.passes}</span></div><div><b>${sm.seconds}</b><span>${ui.seconds}</span></div>
            <div><b>${sm.players_involved}</b><span>${ui.players}</span></div><div><b>${sm.progress_m}</b><span>${ui.metres}</span></div>
            <div><b>${sm.box_entries}</b><span>${ui.entries}</span></div>
          </div>
          <p class="an-origin">${origin}</p>
          <div class="patterns">${a.patterns.map((pt, i) => `<button type="button" class="pat${S.an.pin === i ? " on" : ""}" data-i="${i}">
            <span class="l"><i></i>${esc((copy[i] || {}).label || (PATTERN[pt.key] || {})[lang] || pt.key)}${pt.facts.times > 1 ? ` <span class="meta">×${pt.facts.times}</span>` : ""}</span>
            <span class="str" title="strength"><i style="width:${Math.round(pt.strength * 100)}%"></i></span>
            <span class="x">${esc((copy[i] || {}).text || "")}</span></button>`).join("")}</div>
        </div>
      </div>`;
    body.querySelectorAll(".an-pick .btn").forEach((b) => b.addEventListener("click", () => { S.an.id = b.dataset.id; S.an.auto = false; S.an.pin = null; renderAnalysis(); }));
    body.querySelectorAll("#anView button").forEach((b) => b.addEventListener("click", () => { S.an.frame = b.dataset.v === "frame"; renderAnalysis(); }));
    body.querySelectorAll(".pat").forEach((b) => {
      const steps = a.patterns[Number(b.dataset.i)].steps;
      b.addEventListener("mouseenter", () => highlight(steps));
      b.addEventListener("mouseleave", () => highlight(S.an.pin != null ? a.patterns[S.an.pin].steps : []));
      b.addEventListener("click", () => { const i = Number(b.dataset.i); S.an.pin = S.an.pin === i ? null : i; renderAnalysis(); });
    });
    if (S.an.pin != null && a.patterns[S.an.pin]) highlight(a.patterns[S.an.pin].steps);
  }
  function chancesHtml() {
    const ui = UI[S.profile.lang], lang = S.profile.lang, m = S.match;
    const all = STATIC ? (TL.chances || []).filter((c) => c.t <= S.t) : ((S.snapshot && S.snapshot.chances) || []);
    if (!all.length) return `<div class="empty">${ui.empty}</div>`;
    const teams = [m.home.code, m.away.code];
    const count = (team, key) => all.filter((c) => c.team === team && c.patterns.includes(key)).length;
    const keys = Object.keys(PATTERN).filter((k) => teams.some((t) => count(t, k)));
    keys.sort((x, y) => (count(teams[0], y) + count(teams[1], y)) - (count(teams[0], x) + count(teams[1], x)));
    const max = Math.max(1, ...keys.flatMap((k) => teams.map((t) => count(t, k))));
    let dots = "";
    for (const c of all) {
      const r = 0.9 + Math.sqrt(c.xg) * 3.2, col = teamColor(c.team);
      dots += c.outcome === "goal"
        ? `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="${col}" stroke="var(--ink)" stroke-width=".6"><title>${esc(c.minute)} ${esc(name(c.player))} · ${c.xg} xG</title></circle>`
        : `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="${col}" fill-opacity=".35" stroke="${col}" stroke-width=".35"><title>${esc(c.minute)} ${esc(name(c.player))} · ${c.xg} xG</title></circle>`;
    }
    const sp = (t) => all.filter((c) => c.team === t && ["corner", "free_kick"].includes(c.origin)).length;
    const head = teams.map((t) => {
      const mine = all.filter((c) => c.team === t), g = mine.filter((c) => c.outcome === "goal").length;
      return `<span style="color:${teamColor(t)}">${esc(t === m.home.code ? m.home.short : m.away.short)}</span><span class="meta"> ${ui.shots} ${mine.length} · ${ui.goals} ${g} · ${ui.setp} ${sp(t)} · ${ui.openp} ${mine.length - sp(t)}</span>`;
    });
    return `<div class="an-grid">
      <div><div class="an-pitch"><svg viewBox="50 -3 58 74" role="img" aria-label="Shot map">${pitchLines()}${dots}</svg></div>
        <div class="an-note">${esc(ui.allNote)}</div></div>
      <div><div class="meta" style="display:grid;gap:4px;margin-bottom:12px">${head.map((h) => `<div>${h}</div>`).join("")}</div>
        <div class="creation">${keys.map((k) => `<div class="row"><span>${esc(PATTERN[k][lang])}</span><span class="bars">${teams.map((t) => `<i style="width:${(100 * count(t, k)) / max}%;background:${teamColor(t)}"></i>`).join("")}</span><span class="n">${teams.map((t) => count(t, k)).join("·")}</span></div>`).join("")}</div></div>
    </div>`;
  }
  $("anTabs").addEventListener("click", (e) => { const v = e.target.closest("button")?.dataset.v; if (v) { S.an.tab = v; renderAnalysis(); } });
  function showAnalysis(momentId) {
    S.an.id = momentId; S.an.auto = false; S.an.tab = "one"; S.an.pin = null;
    renderAnalysis();
    $("analysisPanel").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ------------------------------------------------------------------ why drawer
  function openDrawer(rec) {
    const d = $("drawer");
    const ev = rec.evidence || {};
    const items = Object.entries(ev).filter(([k, v]) => v !== null && typeof v !== "object" || k === "why_tags" || k === "build_up");
    const fmtV = (v) => Array.isArray(v) ? v.join(", ").replace(/_/g, " ") : typeof v === "boolean" ? (v ? "yes" : "no") : v;
    const src = rec.source === "foundry" ? '<span class="badge ai">Foundry agent</span>' : rec.source === "producer" ? '<span class="badge">Producer edit</span>' : '<span class="badge">Template</span>';
    const ver = (rec.verifier || []).length ? `<span class="badge no">Verifier fell back: ${esc(rec.verifier[0])}</span>` : '<span class="badge ok">Verified against evidence</span>';
    const ctx = rec.context || {};
    d.innerHTML = `<button class="btn close" type="button" id="closeDrawer">Close</button>
      <div class="sec">${esc(rec.minute)} · ${esc((LABELS[rec.type] || {}).en || rec.type)}</div>
      <h3>${esc(rec.headline)}</h3>
      <div class="why">${esc(rec.why || rec.body)}</div>
      <div class="chips">${src}${ver}<span class="badge">${esc(rec.slot.replace("_", " "))}</span>${rec.latency_ms != null ? `<span class="badge">${rec.latency_ms} ms</span>` : ""}</div>
      ${rec.analysis ? `<button class="btn primary" type="button" id="toAnalysis" style="justify-self:start">See how it was built</button>` : ""}
      <div class="sec">Evidence from the stats engine</div>
      <dl>${items.map(([k, v]) => `<dt>${esc(EV_LABELS[k] || k.replace(/_/g, " "))}</dt><dd>${esc(String(fmtV(v)))}</dd>`).join("")}</dl>
      <div class="sec">Match context at the moment</div>
      <dl><dt>Score</dt><dd>${ctx.score ? Object.values(ctx.score).join("-") : "-"}</dd><dt>Home threat share</dt><dd>${ctx.momentum_home != null ? Math.round(ctx.momentum_home * 100) + "%" : "-"}</dd><dt>Rhythm</dt><dd>${esc(ctx.control_label || "-")} (${ctx.control_index ?? "-"})</dd></dl>
      <details><summary>Overlay JSON sent to the renderer</summary><pre>${esc(JSON.stringify({ ...rec, evidence: undefined, context: undefined, analysis: undefined }, null, 2))}</pre></details>`;
    d.hidden = false;
    $("closeDrawer").addEventListener("click", () => { d.hidden = true; });
    if ($("toAnalysis")) $("toAnalysis").addEventListener("click", () => { d.hidden = true; showAnalysis(rec.moment_id); });
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
    $("srcTag").textContent = "Synthetic match, replay";
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
