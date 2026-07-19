let state = null;
let selectedCounty = null;
let selectedArmy = null;
let selectedSave = null;
let activeTab = "player";

// ── API 通信 ─────────────────────────────────
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
  if (s.pending_events && s.pending_events.length) {
    showEvent(s.pending_events[0]);
  } else {
    hideEvent();
  }
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

// ── 渲染主入口 ─────────────────────────────────
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

  renderPlayerSelect();
  renderPlayerDetail();
  renderLaws();
  renderMap();
  renderCounty();
  renderArmyDetail();
  renderWars();
  renderFactions();
  renderSaves();
  renderLists();
  renderSchemes();
  renderCouncil();
  renderClaims();
  renderDiplomacy();
  renderCountyBuildings();
}

// ── 玩家选择 ─────────────────────────────────
function renderPlayerSelect() {
  const sel = document.getElementById("player-select");
  const cur = sel.value;
  sel.innerHTML = "";
  for (const r of state.playable || []) {
    const o = document.createElement("option");
    o.value = r.id;
    o.textContent = `${r.name}（${r.title}）`;
    if (state.player && r.id === state.player.id) o.selected = true;
    sel.appendChild(o);
  }
  if (!state.player && cur) sel.value = cur;
}

function renderPlayerDetail() {
  const box = document.getElementById("player-detail");
  const p = state.player;
  box.innerHTML = p
    ? `
      <div class="row"><span class="muted">月入</span><span>${p.income}</span></div>
      <div class="row"><span class="muted">虔诚 / 压力 / 健康</span><span>${p.piety} / ${p.stress} / ${p.health}</span></div>
      <div class="row"><span class="muted">属性</span><span>
        外${p.attrs.diplomacy} 军${p.attrs.martial} 管${p.attrs.stewardship}
        谋${p.attrs.intrigue} 学${p.attrs.learning} 武${p.attrs.prowess}
      </span></div>
    `
    : "";
}

// ── 法律 ─────────────────────────────────
function renderLaws() {
  const box = document.getElementById("laws");
  if (!box) return;
  const p = state.player;
  const laws = p && p.laws ? p.laws : null;
  if (!laws) {
    box.innerHTML = `<div class="muted">无头衔，无法改法</div>`;
    return;
  }
  const successionOptions = [
    ["PRIMOGENITURE", "长子继承"], ["CONFEDERATE_PARTITION", "联邦分割"],
    ["ELECTIVE", "选举君主"], ["HOUSE_SENIORITY", "家族长老"], ["ULTIMOGENITURE", "幼子继承"],
  ];
  const crownOptions = [[0,"自治王权"],[1,"有限王权"],[2,"高度王权"],[3,"绝对王权"]];
  const genderOptions = [
    ["AGNATIC","男系继承"],["AGNATIC_COGNATIC","男系优先"],
    ["ABSOLUTE_COGNATIC","绝对双系"],["ENATIC","女系继承"],
  ];
  const pick = (opts, current, kind) =>
    opts.map(([val, label]) =>
      `<button class="mini law-btn${String(current)===String(val)?" selected":""}" data-law="${val}" data-kind="${kind}">${label}</button>`
    ).join(" ");
  box.innerHTML = `
    <div class="row"><span class="muted">继承法</span><span>${pick(successionOptions, laws.succession, "succession")}</span></div>
    <div class="row"><span class="muted">王权</span><span>${pick(crownOptions, laws.crown_authority, "crown")}</span></div>
    <div class="row"><span class="muted">性别法</span><span>${pick(genderOptions, laws.gender_law, "gender")}</span></div>
  `;
  box.querySelectorAll(".law-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.dataset.kind;
      const val = btn.dataset.law;
      if (kind === "succession") act({ action: "set_succession_law", law: val });
      else if (kind === "crown") act({ action: "set_crown_authority", level: Number(val) });
      else if (kind === "gender") act({ action: "set_gender_law", law: val });
    });
  });
}

// ── 地图 ─────────────────────────────────
function renderMap() {
  const svg = document.getElementById("map");
  const parts = [];
  parts.push(`<rect x="0" y="0" width="820" height="720" fill="#121820"/>`);
  parts.push(`<rect x="60" y="${state.sea.y - 8}" width="700" height="18" fill="#1a3a52" opacity="0.55" rx="4"/>`);
  parts.push(`<text class="sea-label" x="410" y="${state.sea.y + 5}" text-anchor="middle">${state.sea.label}</text>`);
  for (const e of state.edges || []) {
    parts.push(`<line class="edge" x1="${e.x1}" y1="${e.y1}" x2="${e.x2}" y2="${e.y2}"/>`);
  }
  for (const c of state.counties || []) {
    const cls = ["county", selectedCounty === c.id ? "selected" : "", c.is_player ? "player-land" : ""].filter(Boolean).join(" ");
    parts.push(`<polygon class="${cls}" data-id="${c.id}" points="${c.points}" fill="${c.color}" opacity="0.92"/>`);
    parts.push(`<text class="county-label" x="${c.cx}" y="${c.cy + 4}">${c.name}</text>`);
    if (c.siege) {
      const pct = Math.min(100, (c.siege.progress / c.siege.required) * 100);
      parts.push(`<rect x="${c.cx - 28}" y="${c.cy + 12}" width="56" height="5" fill="#000" opacity="0.5" rx="2"/>`);
      parts.push(`<rect x="${c.cx - 28}" y="${c.cy + 12}" width="${56 * pct / 100}" height="5" fill="#e35d6a" rx="2"/>`);
    }
  }
  for (const a of state.armies || []) {
    const cls = ["army", a.is_player ? "player" : "", selectedArmy === a.id ? "selected" : "", a.supply_low ? "low-supply" : "", a.in_enemy ? "in-enemy" : ""].filter(Boolean).join(" ");
    let fill = a.is_player ? "#d4a017" : "#3d8bfd";
    if (a.supply_low) fill = "#c44b3c";
    else if (a.in_enemy) fill = a.is_player ? "#c47a10" : "#2f6fc4";
    const menK = a.men >= 1000 ? (a.men / 1000).toFixed(1) + "k" : String(a.men);
    const sup = Math.max(0, Math.min(100, a.supply != null ? a.supply : 100));
    const barColor = sup < 25 ? "#e35d6a" : sup < 50 ? "#e0a84a" : "#3ecf8e";
    parts.push(`
      <g class="${cls}" data-army="${a.id}" transform="translate(${a.cx},${a.cy})">
        <circle r="12" fill="${fill}" stroke="${a.in_enemy ? "#ff8a80" : "none"}" stroke-width="1.5"/>
        <text y="4">${menK}</text>
        <rect x="-14" y="14" width="28" height="3.5" fill="#000" opacity="0.45" rx="1"/>
        <rect x="-14" y="14" width="${(28 * sup) / 100}" height="3.5" fill="${barColor}" rx="1"/>
      </g>
    `);
  }
  svg.innerHTML = parts.join("");
  svg.querySelectorAll(".county").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const id = Number(el.dataset.id);
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

// ── 省份详情 ─────────────────────────────────
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
    <div class="muted" style="margin-top:6px">当前军团: ${
      army ? `${army.name} (${army.men}人 · 补给 ${army.supply ?? "—"} · 士气 ${army.morale ?? "—"}${army.in_enemy ? " · 敌境" : ""})` : "未选择"
    }</div>
  `;
}

function renderCountyBuildings() {
  const box = document.getElementById("county-buildings");
  if (!box) return;
  const c = (state.counties || []).find((x) => x.id === selectedCounty);
  if (!c) {
    box.innerHTML = `<span class="muted">选择省份查看建筑</span>`;
    return;
  }
  const buildings = c.buildings || [];
  box.innerHTML = buildings.length
    ? buildings.map((b) => `<span class="tag">${escapeHtml(b)}</span>`).join(" ")
    : `<span class="muted">无建筑</span>`;
}

// ── 军团详情 ─────────────────────────────────
function renderArmyDetail() {
  const box = document.getElementById("army-detail");
  const cmdSel = document.getElementById("commander-select");
  if (!box) return;
  const army = (state.armies || []).find((x) => x.id === selectedArmy);
  if (!army || !army.is_player) {
    box.innerHTML = `<span class="muted">未选择己方军团</span>`;
    if (cmdSel) cmdSel.innerHTML = "";
    return;
  }
  box.innerHTML = `
    <div><strong>${army.name}</strong></div>
    <div class="row"><span class="muted">兵力</span><span>${army.men}</span></div>
    <div class="row"><span class="muted">状态</span><span>${army.status}</span></div>
    <div class="row"><span class="muted">补给 / 士气</span><span>${army.supply} / ${army.morale}</span></div>
    <div class="row"><span class="muted">位置</span><span>${army.location_name}</span></div>
  `;
  // 填充指挥官候选
  if (cmdSel) {
    const chars = (state.characters || []).filter((c) => c.is_ruler === false || c.id === state.player.id);
    cmdSel.innerHTML = chars.map((c) => `<option value="${c.id}">${c.name} (军${c.attrs ? c.attrs.martial : 0})</option>`).join("");
  }
}

// ── 战争 ─────────────────────────────────
function renderWars() {
  const box = document.getElementById("wars");
  const wars = (state.wars || []).filter((w) => w.active);
  if (!wars.length) {
    box.innerHTML = `<div class="muted">无进行中战争</div>`;
    return;
  }
  box.innerHTML = wars.map((w) => {
    const wpBtn = w.involves_player && w.can_white_peace
      ? `<button class="mini" data-white-peace="${w.id}">白和</button>`
      : w.involves_player ? `<span class="muted"> · ${w.months || 0}月</span>` : "";
    return `<div class="list-row"><span><span class="tag war">${w.cb}</span>${w.attacker} vs ${w.defender} · 分 ${w.warscore}${w.involves_player ? " · 你" : ""}</span>${wpBtn}</div>`;
  }).join("");
  box.querySelectorAll("[data-white-peace]").forEach((btn) => {
    btn.addEventListener("click", () => act({ action: "white_peace", war_id: Number(btn.dataset.whitePeace) }));
  });
}

// ── 派系 ─────────────────────────────────
function renderFactions() {
  const box = document.getElementById("factions");
  if (!box) return;
  const factions = state.factions || [];
  if (!factions.length) {
    box.innerHTML = `<div class="muted">无活跃派系</div>`;
    return;
  }
  box.innerHTML = factions.map((f) =>
    `<div class="list-row"><span><span class="tag">${f.kind}</span>成员${f.members} · 力${f.power} · 不满${f.discontent}${f.ultimatum ? ' <span class="tag war">最后通牒</span>' : ""}</span><button class="mini" data-appease="${f.id}">安抚(25金)</button></div>`
  ).join("");
  box.querySelectorAll("[data-appease]").forEach((btn) => {
    btn.addEventListener("click", () => act({ action: "appease_faction", faction_id: Number(btn.dataset.appease) }));
  });
}

// ── 阴谋 ─────────────────────────────────
function renderSchemes() {
  // 发起阴谋的目标选择
  const targetSel = document.getElementById("scheme-target-select");
  const typeSel = document.getElementById("scheme-type-select");
  if (targetSel) {
    const others = (state.characters || []).filter((c) => c.id !== (state.player ? state.player.id : -1));
    targetSel.innerHTML = others.map((c) => `<option value="${c.id}">${c.name}（${c.title || "无头衔"}）</option>`).join("");
  }
  if (typeSel) {
    typeSel.innerHTML = (state.scheme_types || []).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  }
  // 进行中阴谋列表
  const list = document.getElementById("scheme-list");
  const schemes = state.player_schemes || [];
  if (!schemes.length) {
    list.innerHTML = `<div class="muted">无进行中阴谋</div>`;
    return;
  }
  list.innerHTML = schemes.map((s) => {
    const pct = Math.min(100, s.progress);
    return `<div class="list-row">
      <span><span class="tag">${s.kind_zh}</span>→ ${s.target_name} · 进度 ${s.progress}% · 隐秘 ${s.secrecy}</span>
    </div>`;
  }).join("");
}

// ── 内阁 ─────────────────────────────────
function renderCouncil() {
  const box = document.getElementById("council-list");
  if (!box) return;
  const council = state.player_council;
  if (!council) {
    box.innerHTML = `<div class="muted">无内阁</div>`;
    return;
  }
  const tasks = state.council_tasks || [];
  const chars = (state.characters || []).filter((c) => c.is_ruler === false || c.id === (state.player ? state.player.id : -1));
  box.innerHTML = council.members.map((m) => {
    const taskOpts = tasks.map(([k, v]) => `<option value="${k}"${k === m.task ? " selected" : ""}>${v}</option>`).join("");
    const charOpts = chars.map((c) => `<option value="${c.id}"${c.id === m.holder_id ? " selected" : ""}>${c.name}（${c.attrs ? "外" + c.attrs.diplomacy + " 军" + c.attrs.martial + " 管" + c.attrs.stewardship + " 谋" + c.attrs.intrigue + " 学" + c.attrs.learning : ""}）</option>`).join("");
    return `<div class="council-row">
      <div class="row"><span class="muted">${m.position_zh}</span>
        <select class="council-char" data-position="${m.position}"><option value="">（空缺）</option>${charOpts}</select>
      </div>
      <div class="row"><span class="muted">任务</span>
        <select class="council-task" data-position="${m.position}">${taskOpts}</select>
      </div>
    </div>`;
  }).join("");
  box.querySelectorAll(".council-char").forEach((sel) => {
    sel.addEventListener("change", () => {
      const pos = sel.dataset.position;
      const cid = Number(sel.value) || 0;
      act({ action: "appoint_council", position: pos, character_id: cid });
    });
  });
  box.querySelectorAll(".council-task").forEach((sel) => {
    sel.addEventListener("change", () => {
      act({ action: "assign_council_task", position: sel.dataset.position, task: sel.value });
    });
  });
}

// ── 宣称 ─────────────────────────────────
function renderClaims() {
  const box = document.getElementById("claims");
  if (!box) return;
  const claims = state.player_claims || [];
  if (!claims.length) {
    box.innerHTML = `<div class="muted">无宣称。选中他人省份后可花费 50 金伪造。</div>`;
    return;
  }
  box.innerHTML = claims.map((c) =>
    `<div class="list-row"><span><span class="tag">${c.county_name || c.title_name || "?"}</span>强度 ${c.strength}${c.pressed ? " · 已压" : ""}</span></div>`
  ).join("");
}

// ── 外交 ─────────────────────────────────
function renderDiplomacy() {
  const sel = document.getElementById("dipl-char-select");
  const detail = document.getElementById("dipl-char-detail");
  const treatiesBox = document.getElementById("treaties");
  if (!sel) return;
  const others = (state.characters || []).filter((c) => c.id !== (state.player ? state.player.id : -1));
  const cur = sel.value;
  sel.innerHTML = others.map((c) => `<option value="${c.id}">${c.name}（${c.title || "无"}）</option>`).join("");
  if (cur) sel.value = cur;
  // 角色详情
  const targetId = Number(sel.value);
  const target = others.find((c) => c.id === targetId);
  if (target) {
    const flags = [];
    if (target.relation_allied) flags.push('<span class="tag ok">同盟</span>');
    if (target.relation_rival) flags.push('<span class="tag war">宿敌</span>');
    if (target.relation_at_war) flags.push('<span class="tag war">交战</span>');
    if (target.relation_marriage) flags.push('<span class="tag">联姻</span>');
    detail.innerHTML = `
      <div><strong>${target.name}</strong> ${flags.join("")}</div>
      <div class="row"><span class="muted">头衔</span><span>${target.title || "无"}</span></div>
      <div class="row"><span class="muted">年龄 / 性别</span><span>${target.age} / ${target.gender === "MALE" ? "男" : "女"}</span></div>
      ${target.attrs ? `<div class="row"><span class="muted">属性</span><span>外${target.attrs.diplomacy} 军${target.attrs.martial} 管${target.attrs.stewardship} 谋${target.attrs.intrigue} 学${target.attrs.learning}</span></div>` : ""}
      <div class="row"><span class="muted">金 / 威望</span><span>${target.gold} / ${target.prestige}</span></div>
      <div class="row"><span class="muted">他对你的好感</span><span>${target.opinion_of_player}</span></div>
      <div class="row"><span class="muted">你对他的好感</span><span>${target.player_opinion}</span></div>
      ${target.is_married ? '<div class="muted">已婚</div>' : '<div class="muted">未婚</div>'}
    `;
  } else {
    detail.innerHTML = `<span class="muted">选择一位角色</span>`;
  }
  // 条约
  const treaties = state.treaties || [];
  treatiesBox.innerHTML = treaties.length
    ? treaties.map((t) => `<div class="list-row"><span><span class="tag">${t.kind_zh}</span>${t.other_name} · 至 ${t.expires_year}</span></div>`).join("")
    : `<div class="muted">无条约</div>`;
}

// ── 存档 ─────────────────────────────────
function renderSaves() {
  const box = document.getElementById("saves");
  if (!box) return;
  const saves = state.saves || [];
  if (!saves.length) {
    selectedSave = null;
    box.innerHTML = `<div class="muted">暂无存档</div>`;
    return;
  }
  if (!selectedSave || !saves.some((s) => s.name === selectedSave)) {
    selectedSave = saves[0].name;
  }
  box.innerHTML = saves.map((s) => {
    const cls = s.name === selectedSave ? "save-item selected" : "save-item";
    const date = s.date || "未知日期";
    const broken = s.broken ? ' <span class="tag war">损坏</span>' : "";
    return `<div class="${cls}" data-save="${escapeHtml(s.name)}"><strong>${escapeHtml(s.name)}</strong>${broken}<br><span class="muted">${date} · ${Math.ceil((s.size || 0) / 1024)}KB</span></div>`;
  }).join("");
  box.querySelectorAll("[data-save]").forEach((el) => {
    el.addEventListener("click", () => {
      selectedSave = el.dataset.save;
      renderSaves();
      const input = document.getElementById("save-name");
      if (input) input.value = selectedSave || "";
    });
  });
}

// ── 日志 ─────────────────────────────────
function renderLists() {
  document.getElementById("messages").innerHTML = (state.messages || []).slice().reverse().map((m) => `<div>${escapeHtml(m)}</div>`).join("");
  document.getElementById("log").innerHTML = (state.log || []).slice().reverse().map((m) => `<div>${escapeHtml(m)}</div>`).join("");
}

// ── 工具 ─────────────────────────────────
function escapeHtml(s) {
  return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function showEvent(ev) {
  const overlay = document.getElementById("event-overlay");
  const title = document.getElementById("event-title");
  const desc = document.getElementById("event-desc");
  const choices = document.getElementById("event-choices");
  if (!overlay || !title || !desc || !choices) return;
  title.textContent = ev.title || "事件";
  desc.textContent = ev.description || "";
  choices.innerHTML = "";
  for (const c of ev.choices || []) {
    const btn = document.createElement("button");
    btn.textContent = c.text;
    btn.className = "mini";
    btn.addEventListener("click", () => {
      overlay.style.display = "none";
      act({ action: "resolve_event", event_id: ev.event_id, choice_id: c.id });
    });
    choices.appendChild(btn);
  }
  overlay.style.display = "flex";
}

function hideEvent() {
  const overlay = document.getElementById("event-overlay");
  if (overlay) overlay.style.display = "none";
}

// ── 标签页切换 ─────────────────────────────────
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.toggle("active", c.id === `tab-${tab}`));
}

// ── 事件绑定 ─────────────────────────────────
function bind() {
  // 标签页
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });
  // 时间推进
  document.querySelectorAll(".time-controls button").forEach((btn) => {
    btn.addEventListener("click", () => act({ action: "advance", days: Number(btn.dataset.days) }));
  });
  // 玩家选择
  document.getElementById("player-select").addEventListener("change", (e) => {
    act({ action: "set_player", character_id: Number(e.target.value) });
  });
  // 军团操作
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
  document.getElementById("btn-recruit-knights").addEventListener("click", () => act({ action: "recruit_knights" }));
  document.getElementById("btn-set-commander").addEventListener("click", () => {
    if (!selectedArmy) return alert("请先选择军团");
    const cid = Number(document.getElementById("commander-select").value);
    if (!cid) return alert("请选择指挥官");
    act({ action: "set_commander", army_id: selectedArmy, character_id: cid });
  });
  // 省份操作
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
  document.getElementById("btn-develop").addEventListener("click", () => {
    if (!selectedCounty) return alert("请先选择省份");
    act({ action: "develop_county", county_id: selectedCounty });
  });
  document.getElementById("btn-fabricate").addEventListener("click", () => {
    if (!selectedCounty) return alert("请先选择省份");
    act({ action: "fabricate_claim", county_id: selectedCounty });
  });
  // 外交操作
  document.getElementById("btn-alliance").addEventListener("click", () => {
    const tid = Number(document.getElementById("dipl-char-select").value);
    if (!tid) return alert("请选择目标");
    act({ action: "form_alliance", target_id: tid });
  });
  document.getElementById("btn-non-aggression").addEventListener("click", () => {
    const tid = Number(document.getElementById("dipl-char-select").value);
    if (!tid) return alert("请选择目标");
    act({ action: "form_non_aggression", target_id: tid });
  });
  document.getElementById("btn-marry").addEventListener("click", () => {
    const tid = Number(document.getElementById("dipl-char-select").value);
    if (!tid) return alert("请选择目标");
    act({ action: "arrange_marriage", target_id: tid });
  });
  document.getElementById("btn-gift").addEventListener("click", () => {
    const tid = Number(document.getElementById("dipl-char-select").value);
    if (!tid) return alert("请选择目标");
    const amt = Number(document.getElementById("gift-amount").value) || 50;
    act({ action: "send_gift", target_id: tid, amount: amt });
  });
  document.getElementById("btn-rival").addEventListener("click", () => {
    const tid = Number(document.getElementById("dipl-char-select").value);
    if (!tid) return alert("请选择目标");
    act({ action: "set_rival", target_id: tid });
  });
  // 阴谋操作
  document.getElementById("btn-start-scheme").addEventListener("click", () => {
    const tid = Number(document.getElementById("scheme-target-select").value);
    const kind = document.getElementById("scheme-type-select").value;
    if (!tid) return alert("请选择目标");
    act({ action: "start_scheme", scheme_kind: kind, target_id: tid });
  });
  // 存档操作
  document.getElementById("btn-save").addEventListener("click", () => {
    const name = document.getElementById("save-name").value.trim() || undefined;
    act({ action: "save", name });
  });
  document.getElementById("btn-load").addEventListener("click", () => {
    if (!selectedSave) return alert("请先选择存档");
    act({ action: "load", name: selectedSave });
  });
  document.getElementById("btn-delete-save").addEventListener("click", () => {
    if (!selectedSave) return alert("请先选择存档");
    if (selectedSave === "autosave") return alert("自动存档不能删除");
    if (confirm(`删除存档 ${selectedSave}？`)) act({ action: "delete_save", name: selectedSave });
  });
  document.getElementById("btn-new").addEventListener("click", () => {
    if (confirm("开始新局？")) act({ action: "new_game" });
  });
}

// ── 启动 ─────────────────────────────────
async function boot() {
  bind();
  const s = await apiGet();
  applyState(s);
}

boot().catch((e) => {
  document.body.innerHTML = `<pre style="color:#fff;padding:20px">无法连接后端: ${e}\n请运行 python run_game.py</pre>`;
});
