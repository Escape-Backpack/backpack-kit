/* Hint-page sync: logs a team's run to a stats API (escapepack.ca's workers/stats), lets other
   phones join the same run with a game code, and draws the end-screen comparison.
   Works offline: actions queue in localStorage and are sent when the phone is back online.

     const sync = EBSync.create({ api, backpack, version, locks, key });
     sync.onState(state => ...)     // the run as the server has it, after each send or refresh
     sync.start({ team, session })  // a new run; sync.code is its game code once the server answers
     sync.join(code)                // follow a teammate's run -> state (throws if the code is unknown)
     sync.op({ t: "solve", lock: 2, upto: true })   // also hint / unsolve / pause / resume / finish
     sync.toLocal(serverMs)         // a server timestamp on this phone's clock
     sync.stats()                   // comparison numbers for this run, or null
     sync.leave()                   // stop following (Reset / Play again)

   A copy is served by escapepack.ca as /sync.js for its hand-made Hiking page
   (escapepack-site/tools/build_help.py copies it). */
(function () {
  "use strict";
  const read = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

  function device() {
    const ua = navigator.userAgent;
    return {
      device: /Mobi|Android|iPhone|iPad/i.test(ua) ? "mobile" : "desktop",
      browser: /Edg/i.test(ua) ? "Edge" : /Chrome|CriOS/i.test(ua) ? "Chrome" : /Firefox|FxiOS/i.test(ua) ? "Firefox" : /Safari/i.test(ua) ? "Safari" : "Other",
    };
  }

  function create(cfg) {
    const KEY = cfg.key + ":sync";
    const blank = () => ({ code: "", session: "", offset: s ? s.offset : 0, queue: [], create: null });
    let s = null;
    s = Object.assign(blank(), read(KEY) || {});
    const save = () => write(KEY, s);
    const listeners = [];
    let busy = false, again = false, soon = 0;

    async function call(method, path, body) {
      const t0 = Date.now();
      const res = await fetch(cfg.api + path, {
        method, keepalive: method === "POST",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const t1 = Date.now();
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { const e = new Error(data.error || "HTTP " + res.status); e.status = res.status; throw e; }
      if (data.now) s.offset = Math.round(data.now - (t0 + t1) / 2);
      return data;
    }

    // Send the queue (or just refresh) and hand the server's state to the page.
    async function flush() {
      if (!cfg.api) return null;
      if (busy) { again = true; return null; }
      busy = true;
      try {
        if (s.create) {
          const st = await call("POST", "/runs", Object.assign({}, s.create, { age_ms: Date.now() - s.create.at }));
          s.code = st.code; s.create = null; save();
        }
        if (!s.code) return null;
        const sent = s.queue.slice();
        const ops = sent.map(o => { const c = Object.assign({}, o, { ago: Date.now() - o.ts }); delete c.ts; return c; });
        const st = ops.length ? await call("POST", "/runs/" + s.code + "/ops", { ops }) : await call("GET", "/runs/" + s.code);
        s.queue.splice(0, sent.length); save();
        // Actions made while this request was out would be undone by an older state: wait for the next one.
        if (!s.queue.length) listeners.forEach(f => f(st));
        return st;
      } catch (e) {
        if (e.status === 404 && s.code && !s.create) { s.code = ""; s.queue = []; save(); } // the run is gone
        else if (s.create && e.status && e.status < 500) { s.create = null; save(); } // refused: stop retrying
        return null;
      } finally {
        busy = false;
        if (again) { again = false; schedule(); }
      }
    }
    function schedule(ms) { clearTimeout(soon); soon = setTimeout(flush, ms || 250); }

    const live = () => !!(s.code || s.create);
    setInterval(() => { if (live() && document.visibilityState === "visible") flush(); }, 15000);
    document.addEventListener("visibilitychange", () => { if (live() && document.visibilityState === "visible") flush(); });
    window.addEventListener("online", () => { if (live()) flush(); });
    if (live()) schedule(500);

    return {
      get code() { return s.code; },
      get pending() { return !!s.create; },
      onState(f) { listeners.push(f); },
      start(info) {
        if (!cfg.api) return Promise.resolve(null);
        s = blank();
        s.session = info.session;
        s.create = Object.assign({ backpack: cfg.backpack, version: cfg.version, locks_total: cfg.locks,
          team: info.team || "", team_size: info.team_size || undefined, session_id: info.session, at: Date.now() }, device());
        save();
        return flush();
      },
      async join(code) {
        const st = await call("GET", "/runs/" + String(code).trim().toUpperCase().replace(/[^A-Z0-9]/g, ""));
        if (st.backpack !== cfg.backpack) { const e = new Error("That code is for a different game."); e.status = 404; throw e; }
        s = blank(); s.code = st.code; s.session = st.session_id; save();
        return st;
      },
      op(o) {
        if (!live()) return;
        s.queue.push(Object.assign({}, o, { ts: Date.now() }));
        save(); schedule();
      },
      flush,
      toLocal: ms => (ms == null ? 0 : ms - s.offset),
      async stats() {
        if (!cfg.api) return null;
        try {
          return await call("GET", "/stats?backpack=" + encodeURIComponent(cfg.backpack) + "&version=" + encodeURIComponent(cfg.version)
            + (s.session ? "&session=" + encodeURIComponent(s.session) : ""));
        } catch (e) { return null; }
      },
      leave() { s = blank(); save(); },
    };
  }

  // ---- end-screen comparison (inline styles use the page's own colour variables) ----
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const mins = s => { const m = Math.round(s / 60); return m >= 60 ? Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0") : m + " min"; };
  const WHY = {
    test: "Test runs aren't compared with other teams.",
    unfinished: "Not every lock was marked as solved, so this run isn't compared with other teams.",
    continued: "This run picked up a game already under way, so its time isn't compared with other teams.",
    short: "Runs under 30 minutes aren't compared with other teams.",
    long: "Runs over 4 hours aren't compared with other teams.",
  };

  function strip(totals, mine) {
    const all = totals.concat(mine != null ? [mine] : []);
    const lo = Math.min(...all), hi = Math.max(...all), w = 300, pad = 10;
    const x = t => hi === lo ? w / 2 : pad + (t - lo) / (hi - lo) * (w - 2 * pad);
    const dots = totals.map(t => `<circle cx="${x(t).toFixed(1)}" cy="22" r="4" fill="currentColor" opacity=".45"/>`).join("");
    const me = mine != null ? `<circle cx="${x(mine).toFixed(1)}" cy="22" r="7" fill="var(--brass, #d6ad6b)"/>
      <text x="${x(mine).toFixed(1)}" y="9" text-anchor="middle" font-size="10" fill="var(--brass, #d6ad6b)">YOU</text>` : "";
    return `<svg viewBox="0 0 ${w} 44" width="100%" style="max-width:${w}px;display:block;margin:10px auto 2px;color:var(--muted, #9db0a2)"
      role="img" aria-label="Your time among other teams' times"><line x1="${pad}" y1="22" x2="${w - pad}" y2="22" stroke="currentColor" opacity=".35"/>${dots}${me}
      <text x="${pad}" y="42" font-size="10" fill="currentColor">${esc(mins(lo))}</text><text x="${w - pad}" y="42" text-anchor="end" font-size="10" fill="currentColor">${esc(mins(hi))}</text></svg>`;
  }

  // stats: from sync.stats(). names: lock names, for the best-lock line.
  function compareHTML(stats, names) {
    if (!stats) return `<p style="opacity:.75">Comparison with other teams needs a connection. It will show here once you're back online.</p>`;
    const you = stats.you || {}, min = stats.rules.minRuns;
    let h = "";
    if (you.reason && WHY[you.reason]) h += `<p style="opacity:.8">${WHY[you.reason]}</p>`;
    if (stats.count < min) {
      h += `<p>${stats.count ? `${stats.count} team${stats.count === 1 ? " has" : "s have"} finished so far.` : "You're one of the first teams to play!"}
        Comparisons appear once ${min} teams have finished.</p>`;
      return h;
    }
    if (you.faster_than != null) h += `<p style="font-size:1.15em"><strong>Faster than ${you.faster_than}% of teams</strong></p>`;
    h += strip(stats.totals, you.counts ? you.total : null);
    h += `<p style="opacity:.8">${stats.count} teams · typical time ${esc(mins(stats.median))} · fastest ${esc(mins(stats.fastest))}</p>`;
    const best = (you.locks || []).map((p, i) => [p, i]).filter(([p]) => p != null).sort((a, b) => b[0] - a[0])[0];
    if (best && best[0] >= 50) h += `<p>Your best lock: <strong>${esc(names[best[1]] || "Lock " + (best[1] + 1))}</strong>, faster than ${best[0]}% of teams.</p>`;
    return h;
  }

  window.EBSync = { create, compareHTML };
})();
