let state = null;
let selectedCounty = null;
let selectedArmy = null;

async function apiGet() {
  const r = await fetch("/api/state");
  if (!r.ok) throw new Error("state failed");
  return r.json();
}

async function apiAction(payload) {
  const r = await fetch("/api/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("action failed");
  return r.json();
}

function applyState(s) {
  state = s;
  selectedCounty = s.selected_county;
  selectedArmy = s.selected_army;
  renderAll();
}

async function act(payload) {
  try {
    const s = await apiAction(payload);
    applyState(s);
  } catch (e) {
    console.error(e);
    alert("操作失败: " + e.message);
  }
}

function renderAll() {
  if (!state) return;
  const seasonZh = { SPRING: "春", SUMMER: "夏", AUTUMN: "秋", WINTER: "冬" };
  document.getElementById("date").textContent =
    state.date + (state.season ? ` · ${seasonZh[state.season] || state.season}` : "");
  const p = state.player;
  const exh = state.player_war_exhaustion != null ? ` · 战疲 ${state.player_war_exhaustion}` : "";
  document.getElementById("player-summary").textContent = p
    ? `${p.name} · ${p.title} · 金 ${p.gold} · 威望 ${p.prestige} · 军 ${p.men}${exh}`
    : "无玩家";

  const sel = document.getElementById("player-select");
  const cur = sel.value;
  sel.innerHTML = "";
  for (const r of state.playable || []) {
    const o = document.createElement("option");
    o.value = r.id;
    o.textContent = `${r.name}（${r.title}）`;
    if (p && r.id === p.id) o.selected = true;
    sel.appendChild(o);
  }
  if (!p && cur) sel.value = cur;

  document.getElementById("player-detail").innerHTML = p
    ? `
      <div class="row"><span class="muted">月入</span><span>${p.income}</span></div>
      <div class="row"><span class="muted">虔诚 / 压力 / 健康</span><span>${p.piety} / ${p.stress} / ${p.health}</span></div>
      <div class="row"><span class="muted">属性</span><span>
        外${p.attrs.diplomacy} 军${p.attrs.martial} 管${p.attrs.stewardship}
        谋${p.attrs.intrigue} 学${p.attrs.learning} 武${p.attrs.prowess}
      </span></div>
    `
    : "";

  renderMap();
  renderCounty();
  renderWars();
  renderFactions();
  renderLists();
}

function renderMap() {
  const svg = document.getElementById("map");
  const parts = [];
  parts.push(`<rect x="0" y="0" width="820" height="720" fill="#121820"/>`);
  parts.push(
    `<rect x="60" y="${state.sea.y - 8}" width="700" height="18" fill="#1a3a52" opacity="0.55" rx="4"/>`
  );
  parts.push(
    `<text class="sea-label" x="410" y="${state.sea.y + 5}" text-anchor="middle">${state.sea.label}</text>`
  );

  for (const e of state.edges || []) {
    parts.push(
      `<line class="edge" x1="${e.x1}" y1="${e.y1}" x2="${e.x2}" y2="${e.y2}"/>`
    );
  }

  for (const c of state.counties || []) {
    const cls = [
      "county",
      selectedCounty === c.id ? "selected" : "",
      c.is_player ? "player-land" : "",
    ]
      .filter(Boolean)
      .join(" ");
    parts.push(
      `<polygon class="${cls}" data-id="${c.id}" points="${c.points}" fill="${c.color}" opacity="0.92"/>`
    );
    parts.push(
      `<text class="county-label" x="${c.cx}" y="${c.cy + 4}">${c.name}</text>`
    );
    if (c.siege) {
      const pct = Math.min(100, (c.siege.progress / c.siege.required) * 100);
      parts.push(
        `<rect x="${c.cx - 28}" y="${c.cy + 12}" width="56" height="5" fill="#000" opacity="0.5" rx="2"/>` +
          `<rect x="${c.cx - 28}" y="${c.cy + 12}" width="${56 * pct / 100}" height="5" fill="#e35d6a" rx="2"/>`
      );
    }
  }

  for (const a of state.armies || []) {
    const cls = ["army", a.is_player ? "player" : "", selectedArmy === a.id ? "selected" : ""]
      .filter(Boolean)
      .join(" ");
    const fill = a.is_player ? "#d4a017" : "#3d8bfd";
    const menK = a.men >= 1000 ? (a.men / 1000).toFixed(1) + "k" : String(a.men);
    parts.push(`
      <g class="${cls}" data-army="${a.id}" transform="translate(${a.cx},${a.cy})">
        <circle r="12" fill="${fill}"/>
        <text y="4">${menK}</text>
      </g>
    `);
  }

  svg.innerHTML = parts.join("");

  svg.querySelectorAll(".county").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const id = Number(el.dataset.id);
      // 若已选己方军团，点击省份 = 行军
      if (selectedArmy) {
        const army = (state.armies || []).find((x) => x.id === selectedArmy);
        if (army && army.is_player) {
          act({ action: "move_army", army_id: selectedArmy, county_id: id });
          return;
        }
      }
      act({ action: "select_county", county_id: id });
    });
  });
  svg.querySelectorAll(".army").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      act({ action: "select_army", army_id: Number(el.dataset.army) });
    });
  });
}

function renderCounty() {
  const box = document.getElementById("county-detail");
  const c = (state.counties || []).find((x) => x.id === selectedCounty);
  if (!c) {
    box.innerHTML = `<span class="muted">点击地图选择省份</span>`;
    return;
  }
  const army = (state.armies || []).find((x) => x.id === selectedArmy);
  box.innerHTML = `
    <div><strong>${c.name}</strong> <span class="tag">${c.terrain}</span>
      ${c.is_player ? '<span class="tag ok">己方</span>' : ""}
      ${c.siege ? '<span class="tag war">围城中</span>' : ""}
    </div>
    <div class="row"><span class="muted">领主</span><span>${c.holder_name}</span></div>
    <div class="row"><span class="muted">发展 / 控制</span><span>${c.development} / ${c.control}</span></div>
    <div class="row"><span class="muted">征召 / 税 / 要塞</span><span>${c.levies} / ${c.tax} / ${c.fort}</span></div>
    <div class="row"><span class="muted">驻军标记</span><span>${(c.armies || []).length} 支</span></div>
    <div class="muted" style="margin-top:6px">当前军团: ${
      army ? `${army.name} (${army.men}人 @ ${army.location_name})` : "未选择"
    }</div>
  `;
}

function renderWars() {
  const box = document.getElementById("wars");
  const wars = (state.wars || []).filter((w) => w.active);
  if (!wars.length) {
    box.innerHTML = `<div class="muted">无进行中战争</div>`;
    return;
  }
  box.innerHTML = wars
    .map(
      (w) =>
        `<div><span class="tag war">${w.cb}</span>${w.attacker} vs ${w.defender} · 分 ${w.warscore}${
          w.involves_player ? " · 你" : ""
        }</div>`
    )
    .join("");
}

function renderLists() {
  document.getElementById("messages").innerHTML = (state.messages || [])
    .slice()
    .reverse()
    .map((m) => `<div>${escapeHtml(m)}</div>`)
    .join("");
  document.getElementById("log").innerHTML = (state.log || [])
    .slice()
    .reverse()
    .map((m) => `<div>${escapeHtml(m)}</div>`)
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function bind() {
  document.querySelectorAll(".time-controls button").forEach((btn) => {
    btn.addEventListener("click", () => act({ action: "advance", days: Number(btn.dataset.days) }));
  });
  document.getElementById("player-select").addEventListener("change", (e) => {
    act({ action: "set_player", character_id: Number(e.target.value) });
  });
  document.getElementById("btn-raise").addEventListener("click", () => {
    const cid = selectedCounty || (state.counties.find((c) => c.is_player) || {}).id;
    if (!cid) return alert("请先选择己方省份");
    act({ action: "raise_army", county_id: cid });
  });
  document.getElementById("btn-feast").addEventListener("click", () => act({ action: "hold_feast" }));
  document.getElementById("btn-disband").addEventListener("click", () => {
    if (!selectedArmy) return alert("请先选择军团");
    act({ action: "disband_army", army_id: selectedArmy });
  });
  document.getElementById("btn-move").addEventListener("click", () => {
    if (!selectedArmy || !selectedCounty) return alert("请选择军团和目标省份");
    act({ action: "move_army", army_id: selectedArmy, county_id: selectedCounty });
  });
  document.getElementById("btn-war").addEventListener("click", () => {
    const c = (state.counties || []).find((x) => x.id === selectedCounty);
    if (!c || !c.holder_id) return alert("该省无领主");
    if (c.is_player) return alert("不能对自己宣战");
    act({ action: "declare_war", target_id: c.holder_id });
  });
  document.getElementById("btn-improve").addEventListener("click", () => {
    const c = (state.counties || []).find((x) => x.id === selectedCounty);
    if (!c || !c.holder_id) return alert("该省无领主");
    act({ action: "improve_relations", target_id: c.holder_id });
  });
  document.getElementById("btn-save").addEventListener("click", () => act({ action: "save" }));
  document.getElementById("btn-load").addEventListener("click", () => act({ action: "load" }));
  document.getElementById("btn-new").addEventListener("click", () => {
    if (confirm("开始新局？")) act({ action: "new_game" });
  });
}

async function boot() {
  bind();
  const s = await apiGet();
  applyState(s);
}

boot().catch((e) => {
  document.body.innerHTML = `<pre style="color:#fff;padding:20px">无法连接后端: ${e}\n请运行 python -m ck_engine.ui.server</pre>`;
});
