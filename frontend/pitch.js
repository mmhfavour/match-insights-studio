/* Top-down match feed drawn on canvas from the event stream.
   Ball and players ease towards targets derived from each event; outfield shape follows the ball
   using the same positional model as the simulator, so the feed reads like a tactical camera. */
(function () {
  const L = 105, W = 68, MX = 2, MY = 2, PW = L + 2 * MX, PH = W + 2 * MY;

  class Pitch {
    constructor(canvas, match) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.focus = null;
      this.highlight = new Set();
      this.setMatch(match);
      this.readColors();
      this._colorsAt = performance.now();
      this._last = performance.now();
      const loop = (now) => { this.frame(now); requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
    }

    setMatch(match) {
      this.match = match;
      this.home = match.home.code;
      this.away = match.away.code;
      this.color = { [this.home]: match.home.color, [this.away]: match.away.color };
      this.players = {};
      this.onPitch = { [this.home]: [], [this.away]: [] };
      for (const side of ["home", "away"]) {
        for (const p of match[side].players) { this.players[p.id] = { ...p }; this.onPitch[match[side].code].push(p.id); }
        for (const p of match[side].bench) this.players[p.id] = { ...p };
      }
      this.reset();
    }

    reset() {
      this.period = 1;
      this.poss = this.home;
      this.ball = { x: 52.5, y: 34, tx: 52.5, ty: 34 };
      this.pos = {};
      this.override = {};
      this.lastPass = null;
      this.lastShot = null;
      for (const side of [this.home, this.away]) {
        for (const id of this.onPitch[side]) {
          const p = this.players[id];
          const a = this.toAbs(side, p.base_x * 0.5 + 2, p.base_y);
          this.pos[id] = { x: a[0], y: a[1] };
        }
      }
    }

    attacksRight(team) { return (team === this.home) === (this.period === 1); }
    ownX(team, x) { return this.attacksRight(team) ? x : L - x; }
    toAbs(team, x, y) { return this.attacksRight(team) ? [x, y] : [L - x, W - y]; }

    onEvent(ev, instant = false) {
      const now = performance.now();
      if (ev.period) this.period = ev.period;
      if (ev.type === "kickoff") { this.ball.tx = 52.5; this.ball.ty = 34; }
      if (ev.team && ["pass", "carry", "dribble", "shot", "kickoff"].includes(ev.type)) this.poss = ev.team;
      if (["interception", "tackle", "ball_recovery", "save", "clearance"].includes(ev.type) && ev.team) this.poss = ev.team;
      if (ev.type === "substitution" && ev.d) {
        const off = this.players[ev.d.player_off], on = this.players[ev.d.player_on];
        if (off && on) {
          on.base_x = off.base_x; on.base_y = off.base_y; on.role = off.role;
          const list = this.onPitch[on.team];
          const i = list.indexOf(off.id);
          if (i >= 0) list[i] = on.id;
          this.pos[on.id] = { ...(this.pos[off.id] || { x: 52.5, y: 0 }) };
        }
      }
      if (ev.x != null) {
        const tx = ev.end_x != null && ev.type !== "shot" ? ev.end_x : ev.x;
        const ty = ev.end_y != null && ev.type !== "shot" ? ev.end_y : ev.y;
        this.ball.tx = tx; this.ball.ty = ty;
        if (ev.type === "shot") { this.ball.tx = ev.end_x; this.ball.ty = ev.end_y; }
        if (ev.player) this.override[ev.player] = { x: ev.x, y: ev.y, until: now + 900 };
        if (ev.type === "pass" && ev.d && ev.d.recipient) this.override[ev.d.recipient] = { x: ev.end_x, y: ev.end_y, until: now + 1400 };
        if (ev.type === "carry" || ev.type === "dribble") { if (ev.end_x != null) this.override[ev.player] = { x: ev.end_x, y: ev.end_y, until: now + 1200 }; }
      }
      if (ev.type === "pass") this.lastPass = { x: ev.x, y: ev.y, ex: ev.end_x, ey: ev.end_y, ok: ev.d && ev.d.outcome === "complete", at: now, team: ev.team };
      if (ev.type === "shot") this.lastShot = { x: ev.x, y: ev.y, ex: ev.end_x, ey: ev.end_y, at: now, goal: ev.d && ev.d.outcome === "goal" };
      if (instant) { this.ball.x = this.ball.tx; this.ball.y = this.ball.ty; }
    }

    targetFor(id) {
      const p = this.players[id];
      const ov = this.override[id];
      if (ov && ov.until > performance.now()) return [ov.x, ov.y];
      const team = p.team;
      const inPoss = team === this.poss;
      const bx = this.ownX(team, this.ball.tx), by = this.attacksRight(team) ? this.ball.ty : W - this.ball.ty;
      let px, py;
      if (p.role === "GK") { px = 5 + Math.max(0, bx - 52.5) * 0.12; py = 34 + (by - 34) * 0.1; }
      else {
        px = inPoss ? p.base_x + 6 + (bx - 52.5) * 0.5 : p.base_x - 4 + (bx - 52.5) * 0.45;
        py = p.base_y + (by - 34) * 0.22;
      }
      px = Math.min(97, Math.max(2, px)); py = Math.min(66, Math.max(2, py));
      return this.toAbs(team, px, py);
    }

    snap() {
      for (const side of [this.home, this.away]) for (const id of this.onPitch[side]) { const t = this.targetFor(id); this.pos[id] = { x: t[0], y: t[1] }; }
      this.ball.x = this.ball.tx; this.ball.y = this.ball.ty;
    }

    /** Pixel position of a player inside the canvas box, as fractions for CSS placement. */
    screenFrac(id) {
      const p = this.pos[id];
      if (!p) return null;
      return { x: (p.x + MX) / PW, y: (p.y + MY) / PH };
    }

    readColors() {
      const cs = getComputedStyle(document.documentElement);
      this.c = {
        pitch: cs.getPropertyValue("--pitch").trim() || "#1D5A3D",
        pitch2: cs.getPropertyValue("--pitch-2").trim() || "#205F41",
        line: cs.getPropertyValue("--pitch-line").trim() || "rgba(255,255,255,.5)",
        ink: cs.getPropertyValue("--ink").trim() || "#1B1C19",
        bad: cs.getPropertyValue("--bad").trim() || "#C4432F",
        fill: cs.getPropertyValue("--player-fill").trim() || "#FFFFFF",
        fillInk: cs.getPropertyValue("--player-ink").trim() || "#1B1C19",
      };
    }

    frame(now) {
      const dt = Math.min(0.1, (now - this._last) / 1000);
      this._last = now;
      if (now - this._colorsAt > 1000) { this.readColors(); this._colorsAt = now; }
      const k = Math.min(1, dt * 7), kp = Math.min(1, dt * 3.2);
      this.ball.x += (this.ball.tx - this.ball.x) * k;
      this.ball.y += (this.ball.ty - this.ball.y) * k;
      for (const side of [this.home, this.away]) {
        for (const id of this.onPitch[side]) {
          const t = this.targetFor(id);
          const p = this.pos[id] || (this.pos[id] = { x: t[0], y: t[1] });
          p.x += (t[0] - p.x) * kp; p.y += (t[1] - p.y) * kp;
        }
      }
      this.draw(now);
    }

    draw(now) {
      const cv = this.canvas, dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = cv.clientWidth, h = cv.clientHeight;
      if (!w || !h) return;
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
      const ctx = this.ctx, s = (w / PW) * dpr;
      const X = (x) => (x + MX) * s, Y = (y) => (y + MY) * s;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = this.c.pitch; ctx.fillRect(0, 0, cv.width, cv.height);
      const stripes = 14, sw = L / stripes;
      ctx.fillStyle = this.c.pitch2;
      for (let i = 0; i < stripes; i += 2) ctx.fillRect(X(i * sw), Y(0), sw * s, W * s);

      ctx.strokeStyle = this.c.line; ctx.lineWidth = Math.max(1.2, 0.24 * s);
      ctx.strokeRect(X(0), Y(0), L * s, W * s);
      ctx.beginPath(); ctx.moveTo(X(52.5), Y(0)); ctx.lineTo(X(52.5), Y(W)); ctx.stroke();
      ctx.beginPath(); ctx.arc(X(52.5), Y(34), 9.15 * s, 0, Math.PI * 2); ctx.stroke();
      const dot = (x, y) => { ctx.beginPath(); ctx.arc(X(x), Y(y), 0.35 * s, 0, Math.PI * 2); ctx.fillStyle = this.c.line; ctx.fill(); };
      dot(52.5, 34);
      for (const side of [0, 1]) {
        const x0 = side ? L - 16.5 : 0, x6 = side ? L - 5.5 : 0;
        ctx.strokeRect(X(x0), Y(34 - 20.16), 16.5 * s, 40.32 * s);
        ctx.strokeRect(X(x6), Y(34 - 9.16), 5.5 * s, 18.32 * s);
        const ps = side ? L - 11 : 11; dot(ps, 34);
        ctx.beginPath();
        if (side) ctx.arc(X(ps), Y(34), 9.15 * s, Math.PI - 0.93, Math.PI + 0.93);
        else ctx.arc(X(ps), Y(34), 9.15 * s, -0.93, 0.93);
        ctx.stroke();
        const gx = side ? L : -1.6;
        ctx.strokeRect(X(gx), Y(34 - 3.66), 1.6 * s, 7.32 * s);
      }

      // last pass and shot traces
      if (this.lastPass) {
        const age = (now - this.lastPass.at) / 1000;
        if (age < 1.6 && this.lastPass.ex != null) {
          ctx.save();
          ctx.globalAlpha = Math.max(0, 1 - age / 1.6) * 0.7;
          ctx.strokeStyle = this.lastPass.ok ? this.c.ink : this.c.bad;
          ctx.setLineDash([0.9 * s, 0.7 * s]); ctx.lineWidth = 0.26 * s; ctx.lineCap = "round";
          ctx.beginPath(); ctx.moveTo(X(this.lastPass.x), Y(this.lastPass.y)); ctx.lineTo(X(this.lastPass.ex), Y(this.lastPass.ey)); ctx.stroke();
          ctx.restore();
        }
      }
      if (this.lastShot) {
        const age = (now - this.lastShot.at) / 1000;
        if (age < 2.4) {
          ctx.save();
          ctx.globalAlpha = Math.max(0, 1 - age / 2.4);
          ctx.strokeStyle = this.c.ink; ctx.lineWidth = 0.42 * s; ctx.lineCap = "round";
          ctx.beginPath(); ctx.moveTo(X(this.lastShot.x), Y(this.lastShot.y)); ctx.lineTo(X(this.lastShot.ex), Y(this.lastShot.ey)); ctx.stroke();
          ctx.restore();
        }
      }

      // players
      const r = 1.45 * s;
      const numFont = `700 ${Math.round(1.45 * s)}px Figtree, system-ui, sans-serif`;
      ctx.font = numFont;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      for (const side of [this.home, this.away]) {
        for (const id of this.onPitch[side]) {
          const p = this.pos[id], pl = this.players[id];
          if (!p) continue;
          const isFocus = id === this.focus, hl = this.highlight.has(id);
          if (isFocus || hl) {
            ctx.beginPath(); ctx.arc(X(p.x), Y(p.y), r + 0.85 * s, 0, Math.PI * 2);
            ctx.strokeStyle = this.c.ink; ctx.lineWidth = 0.3 * s; ctx.stroke();
          }
          // A soft drop shadow, then a white disc ringed in the team colour, like a player avatar.
          ctx.beginPath(); ctx.arc(X(p.x), Y(p.y) + 0.22 * s, r, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(20,30,20,.16)"; ctx.fill();
          ctx.beginPath(); ctx.arc(X(p.x), Y(p.y), r, 0, Math.PI * 2);
          ctx.fillStyle = this.c.fill; ctx.fill();
          ctx.lineWidth = 0.42 * s; ctx.strokeStyle = this.color[side]; ctx.stroke();
          ctx.fillStyle = this.c.fillInk; ctx.fillText(String(pl.number), X(p.x), Y(p.y) + 0.1 * s);
          if (isFocus) {
            ctx.font = `600 ${Math.round(1.4 * s)}px Figtree, system-ui, sans-serif`;
            const label = pl.short, tw = ctx.measureText(label).width + 1.4 * s, ty = Y(p.y) + r + 1.9 * s;
            ctx.fillStyle = this.c.ink;
            ctx.beginPath(); ctx.roundRect(X(p.x) - tw / 2, ty - 1.05 * s, tw, 2.1 * s, 1.05 * s); ctx.fill();
            ctx.fillStyle = this.c.fill; ctx.fillText(label, X(p.x), ty + 0.08 * s);
            ctx.font = numFont;
          }
        }
      }
      // ball
      ctx.beginPath(); ctx.arc(X(this.ball.x), Y(this.ball.y), 0.75 * s, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff"; ctx.fill(); ctx.lineWidth = 0.24 * s; ctx.strokeStyle = this.c.ink; ctx.stroke();
    }
  }

  window.Pitch = Pitch;
})();
