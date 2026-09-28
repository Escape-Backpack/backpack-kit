// Shared by index.html (design board) and play.html (play-test).
"use strict";

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const asList = v => v == null || v === "" ? [] : Array.isArray(v) ? v : [v];

// ---------- tiny markdown ----------
// idFn(id) renders a record ID found in the text; omit it to leave IDs as plain text.
function inline(s, idFn) {
  const codes = [];
  s = esc(s).replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, t, u) => /^(https?:|#)/.test(u) ? `<a href="${u}" target="_blank" rel="noopener">${t}</a>` : `<a href="../${u}" target="_blank">${t}</a>`);
  if (idFn) s = s.replace(/(^|[^\w-])((?:PR|ST|PZ|PP|Q|AS)-\d{3,})\b/g, (m, pre, id) => pre + idFn(id));
  return s.replace(/\u0000(\d+)\u0000/g, (m, i) => `<code>${codes[i]}</code>`);
}
function md(src, idFn) {
  src = String(src || "").replace(/<!--[^]*?-->/g, "");
  let html = "", para = [], list = null, code = null;
  const flushP = () => { if (para.length) { html += `<p>${inline(para.join(" "), idFn)}</p>`; para = []; } };
  const flushL = () => { if (list) { html += `<${list.t}>${list.items.map(i => `<li>${inline(i, idFn)}</li>`).join("")}</${list.t}>`; list = null; } };
  for (const ln of String(src || "").replace(/\r/g, "").split("\n")) {
    if (code) { if (/^```/.test(ln)) { html += `<pre><code>${esc(code.join("\n"))}</code></pre>`; code = null; } else code.push(ln); continue; }
    let m;
    if (/^```/.test(ln)) { flushP(); flushL(); code = []; continue; }
    if ((m = ln.match(/^(#{1,4})\s+(.*)/))) { flushP(); flushL(); const n = Math.min(m[1].length + 2, 6); html += `<h${n}>${inline(m[2], idFn)}</h${n}>`; continue; }
    if ((m = ln.match(/^\s*([-*]|\d+\.)\s+(.*)/))) {
      flushP(); const t = /\d/.test(m[1]) ? "ol" : "ul";
      if (!list || list.t !== t) { flushL(); list = { t, items: [] }; }
      list.items.push(m[2]); continue;
    }
    if ((m = ln.match(/^>\s?(.*)/))) { flushP(); flushL(); html += `<blockquote>${inline(m[1], idFn)}</blockquote>`; continue; }
    if (!ln.trim()) { flushP(); flushL(); continue; }
    if (list && /^\s{2,}/.test(ln)) { list.items[list.items.length - 1] += " " + ln.trim(); continue; }
    flushL(); para.push(ln.trim());
  }
  if (code) html += `<pre><code>${esc(code.join("\n"))}</code></pre>`;
  flushP(); flushL();
  return html;
}

// Text of a "## Heading" section in a record body (up to the next ## heading), or "".
function mdSection(body, heading) {
  const lines = String(body || "").replace(/\r/g, "").split("\n");
  const want = heading.trim().toLowerCase();
  let out = null;
  for (const ln of lines) {
    const m = ln.match(/^##\s+(.*)/);
    if (m) { if (out) break; if (m[1].trim().toLowerCase() === want) out = []; continue; }
    if (out) out.push(ln);
  }
  return out ? out.join("\n").trim() : "";
}
// Items of a list section, e.g. the "## Hints" ladder. Empty items are dropped.
function mdListItems(section) {
  return section.split("\n").map(l => l.match(/^\s*(?:[-*]|\d+\.)\s*(.*)$/)).filter(m => m && m[1].trim()).map(m => m[1].trim());
}
