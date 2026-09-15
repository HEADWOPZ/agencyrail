const state = {
  meta: null,
  overview: null,
  filter: "all",
  query: "",
  selected: null,
  detail: null,
  artifactKind: "audit",
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail || JSON.stringify(body);
    } catch {
      message = await res.text();
    }
    throw new Error(message);
  }
  return res.json();
}

function stationButtons(counts) {
  const stations = ["intake", "audit", "mockup", "outreach", "negotiation", "retainer"];
  const root = $("stations");
  root.innerHTML = "";
  const all = buttonStation("all", Object.values(counts).reduce((a, b) => a + b, 0), state.filter === "all");
  root.appendChild(all);
  for (const name of stations) {
    root.appendChild(buttonStation(name, counts[name] || 0, state.filter === name));
  }
}

function buttonStation(name, count, active) {
  const btn = document.createElement("button");
  btn.className = `station${active ? " active" : ""}`;
  btn.type = "button";
  btn.innerHTML = `<b>${count}</b><span>${name}</span>`;
  btn.addEventListener("click", () => {
    state.filter = name;
    renderLeads();
    stationButtons(state.overview.counts);
  });
  return btn;
}

function renderLeads() {
  const list = $("lead-list");
  const query = state.query.trim().toLowerCase();
  const leads = (state.overview?.leads || []).filter((lead) => {
    if (state.filter !== "all" && lead.status !== state.filter) return false;
    if (!query) return true;
    return [lead.slug, lead.org, lead.name, lead.segment, lead.chain]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
  list.innerHTML = "";
  if (!leads.length) {
    list.innerHTML = `<p class="empty">No leads on this station. Seed the rail or open an intake.</p>`;
    return;
  }
  for (const lead of leads) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `lead-card${state.selected === lead.slug ? " active" : ""}`;
    btn.innerHTML = `
      <div class="row">
        <strong>${esc(lead.org)}</strong>
        <span class="badge">${esc(lead.status)}</span>
      </div>
      <div class="row muted">
        <span>${esc(lead.name)} · ${esc(lead.segment)}/${esc(lead.chain)}</span>
        <span>${lead.score == null ? "—" : lead.score}</span>
      </div>
    `;
    btn.addEventListener("click", () => selectLead(lead.slug));
    list.appendChild(btn);
  }
}

async function selectLead(slug) {
  state.selected = slug;
  state.detail = await api(`/api/leads/${slug}`);
  renderLeads();
  renderDetail();
}

function renderDetail() {
  const root = $("detail");
  if (!state.detail) {
    root.innerHTML = `<div class="empty-detail"><p>Select a lead. Agents grind the audit, mockup, outreach, and Loom. You close.</p></div>`;
    return;
  }
  const { lead, artifacts, invoices } = state.detail;
  const kinds = ["audit", "mockup", "outreach", "loom"];
  if (!kinds.includes(state.artifactKind)) state.artifactKind = "audit";
  const current =
    artifacts.find((item) => item.kind === state.artifactKind) || artifacts[0] || null;
  if (current) state.artifactKind = current.kind;

  root.innerHTML = `
    <div class="detail-head">
      <div>
        <h2>${esc(lead.org)}</h2>
        <p class="muted">${esc(lead.name)} · ${esc(lead.email || "no email")}</p>
      </div>
      <label>
        Move
        <select id="move-status">
          ${["intake", "audit", "mockup", "outreach", "negotiation", "retainer", "closed", "lost"]
            .map((status) => `<option value="${status}" ${status === lead.status ? "selected" : ""}>${status}</option>`)
            .join("")}
        </select>
      </label>
    </div>
    <div class="meta">
      <span>${esc(lead.segment)} / ${esc(lead.chain)}</span>
      <span>score ${lead.score == null ? "—" : lead.score}</span>
      <span>${lead.retainer ? `${esc(lead.currency)} ${esc(lead.retainer)} / ${esc(lead.retainer_cadence)}` : "no retainer"}</span>
      <span>${esc(lead.website || "no site")}</span>
    </div>
    <p>${esc(lead.next_action || "")}</p>
    <div class="actions">
      <button class="solid" data-run="audit">Audit</button>
      <button class="ghost" data-run="mockup">Mockup</button>
      <button class="ghost" data-run="outreach">Outreach</button>
      <button class="ghost" data-run="loom">Loom</button>
      <button class="ghost" data-run="pack">Full pack</button>
      <button class="ghost" id="btn-invoice">Invoice</button>
    </div>
    <div class="tabs">
      ${kinds
        .map(
          (kind) =>
            `<button type="button" class="${kind === state.artifactKind ? "active" : ""}" data-kind="${kind}">${kind}</button>`
        )
        .join("")}
    </div>
    <pre class="artifact">${current ? esc(current.body) : "No artifact yet. Run the agent."}</pre>
    <p class="muted">${invoices.length} invoice(s) on this lead</p>
  `;

  $("move-status").addEventListener("change", async (event) => {
    await api(`/api/leads/${lead.slug}/move`, {
      method: "POST",
      body: JSON.stringify({ status: event.target.value }),
    });
    await refresh(lead.slug);
  });

  root.querySelectorAll("[data-run]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await api(`/api/leads/${lead.slug}/run/${btn.dataset.run}`, { method: "POST" });
        state.artifactKind = btn.dataset.run === "pack" ? "loom" : btn.dataset.run;
        await refresh(lead.slug);
      } catch (err) {
        alert(err.message);
      } finally {
        btn.disabled = false;
      }
    });
  });

  root.querySelectorAll("[data-kind]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.artifactKind = btn.dataset.kind;
      renderDetail();
    });
  });

  $("btn-invoice").addEventListener("click", async () => {
    await api(`/api/leads/${lead.slug}/invoices`, { method: "POST", body: "{}" });
    await refresh(lead.slug);
    await openInvoices();
  });
}

async function refresh(slug = state.selected) {
  state.overview = await api("/api/overview");
  stationButtons(state.overview.counts);
  if (slug) {
    state.detail = await api(`/api/leads/${slug}`);
    state.selected = slug;
  }
  renderLeads();
  renderDetail();
}

async function openDigest() {
  const digest = await api("/api/digest");
  $("digest-text").textContent = digest.telegram_text;
  $("digest-path").textContent = digest.path
    ? `Dry-run saved to ${digest.path}`
    : "Dry-run. Telegram was not sent.";
  $("modal-digest").showModal();
}

async function openInvoices() {
  const invoices = await api("/api/invoices");
  const root = $("invoice-list");
  if (!invoices.length) {
    root.innerHTML = `<p class="empty">No invoices yet.</p>`;
  } else {
    root.innerHTML = invoices
      .map(
        (invoice) => `
        <div class="invoice-row">
          <div>
            <strong>${esc(invoice.number)}</strong>
            <div class="muted">${esc(invoice.org || "")} · due ${esc(invoice.due_on)}</div>
          </div>
          <div>
            <div>${esc(invoice.currency)} ${esc(invoice.amount)}</div>
            <div class="${invoice.status === "paid" ? "ok" : "warn"}">${esc(invoice.status)}</div>
          </div>
        </div>`
      )
      .join("");
  }
  $("modal-invoices").showModal();
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function bindChrome() {
  $("btn-new").addEventListener("click", () => $("modal-new").showModal());
  $("btn-digest").addEventListener("click", () => openDigest().catch((err) => alert(err.message)));
  $("btn-invoices").addEventListener("click", () => openInvoices().catch((err) => alert(err.message)));
  $("search").addEventListener("input", (event) => {
    state.query = event.target.value;
    renderLeads();
  });
  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", () => $(btn.dataset.close).close());
  });
  $("form-new").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target).entries());
    const lead = await api("/api/leads", { method: "POST", body: JSON.stringify(data) });
    $("modal-new").close();
    event.target.reset();
    await refresh(lead.slug);
  });
}

async function boot() {
  bindChrome();
  state.meta = await api("/api/meta");
  $("agency-name").textContent = state.meta.agency.name;
  $("agency-tag").textContent = state.meta.agency.tagline;
  $("operator-line").textContent = `${state.meta.operator.name} · ${state.meta.operator.handle} · ${state.meta.operator.telegram}`;
  const overview = await api("/api/overview");
  if (!overview.leads.length) {
    await api("/api/seed", { method: "POST" });
  }
  await refresh();
  if (!state.selected && state.overview.leads.length) {
    await selectLead(state.overview.leads[0].slug);
  }
}

boot().catch((err) => {
  $("lead-list").innerHTML = `<p class="empty">${esc(err.message)}</p>`;
});
