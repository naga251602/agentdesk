const $ = (id) => document.getElementById(id);

async function jget(url) { const r = await fetch(url); return r.json(); }
async function jpost(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

async function refresh() {
  const h = await jget("/health");
  $("health").textContent =
    `${h.status} · v${h.version} · ${h.documents} docs · ${h.chunks} chunks · mode: ${h.llm_mode}`;
  $("stats").textContent = JSON.stringify(await jget("/stats"), null, 2);
  const docs = await jget("/documents");
  $("docs").innerHTML = docs.length
    ? docs.map(d => `<div class="cite">${d.source} — ${d.chunks} chunks</div>`).join("")
    : '<div class="muted">No documents yet — load the sample docs.</div>';
  const esc = await jget("/escalations");
  $("escCount").textContent = esc.length ? `(${esc.length} open)` : "";
  $("escalations").innerHTML = esc.length
    ? esc.map(t => `<div class="ticket"><b>${t.ticket_id}</b> · confidence ${t.confidence}
        <br>${t.question}<br>
        <button onclick="resolveTicket('${t.ticket_id}')">Mark resolved</button></div>`).join("")
    : '<div class="muted">Queue is empty.</div>';
}

async function resolveTicket(id) {
  await jpost(`/escalations/${id}/resolve`, { resolution: "Handled by human agent" });
  refresh();
}

$("sampleBtn").onclick = async () => { await jpost("/ingest/sample"); refresh(); };

$("askBtn").onclick = async () => {
  const q = $("question").value.trim();
  if (!q) return;
  $("answer").innerHTML = '<div class="muted">Thinking…</div>';
  const res = await jpost("/ask", { question: q, customer: $("customer").value || "anonymous" });
  if (res.status === "escalated") {
    $("answer").innerHTML =
      `<div class="answer"><span class="conf bad">Escalated to a human</span>
       (confidence ${res.confidence} &lt; 0.70) — ticket <b>${res.ticket.ticket_id}</b>
       created with the retrieval trace attached.</div>`;
  } else {
    const cites = res.citations.map(c =>
      `<div class="cite">[${c.source}] ${c.heading} · score ${c.score}</div>`).join("");
    $("answer").innerHTML =
      `<div class="answer"><span class="conf ok">Confidence ${res.confidence}</span>
       · ${res.mode} mode · ${res.latency_ms} ms ${res.cached ? "· cached" : ""}
       <p>${res.answer}</p>${cites}</div>`;
  }
  refresh();
};

$("docBtn").onclick = async () => {
  const source = $("docSource").value.trim() || "document.md";
  const text = $("docText").value.trim();
  if (!text) return;
  await jpost("/documents", { source, text });
  $("docText").value = "";
  refresh();
};

$("evalBtn").onclick = async () => {
  $("evalOut").textContent = "Running golden set…";
  const report = await jpost("/evals/run");
  const { per_case, ...summary } = report;
  $("evalOut").textContent = JSON.stringify(summary, null, 2);
  refresh();
};

refresh();
