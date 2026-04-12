// ===== 状态 =====
const state = {
  xp: parseInt(localStorage.getItem("qq_xp") || "0"),
  done: JSON.parse(localStorage.getItem("qq_done") || "[]"),
  badges: JSON.parse(localStorage.getItem("qq_badges") || "[]"),
  factors: [],
};

const BADGE_RULES = [
  { id: "first_step", icon: "🎓", name: "迈出第一步", check: s => s.done.length >= 1 },
  { id: "half_way",   icon: "⭐", name: "半程学者",   check: s => s.done.length >= 3 },
  { id: "graduate",   icon: "🏆", name: "因子毕业生", check: s => s.done.length >= 5 },
  { id: "lab_rat",    icon: "🧪", name: "实验室常客", check: s => s.xp >= 50 },
  { id: "master",     icon: "👑", name: "因子大师",   check: s => s.xp >= 100 },
];

function save() {
  localStorage.setItem("qq_xp", state.xp);
  localStorage.setItem("qq_done", JSON.stringify(state.done));
  localStorage.setItem("qq_badges", JSON.stringify(state.badges));
  renderHud();
}

function addXp(n) {
  state.xp += n;
  for (const b of BADGE_RULES) {
    if (b.check(state) && !state.badges.includes(b.id)) {
      state.badges.push(b.id);
      toast(`🎖️ 解锁徽章：${b.icon} ${b.name}`);
    }
  }
  save();
}

function renderHud() {
  document.getElementById("xp").textContent = state.xp;
  const lvl = 1 + Math.floor(state.xp / 30);
  document.getElementById("level").textContent = lvl;
  const pct = Math.min(100, ((state.xp % 30) / 30) * 100);
  document.getElementById("xpbar").style.width = pct + "%";
  const bd = document.getElementById("badges");
  bd.innerHTML = "";
  for (const b of BADGE_RULES) {
    const owned = state.badges.includes(b.id);
    const span = document.createElement("span");
    span.className = "text-lg badge " + (owned ? "" : "opacity-20 grayscale");
    span.textContent = b.icon;
    span.title = b.name;
    bd.appendChild(span);
  }
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "fixed top-20 right-6 bg-amber-500 text-slate-900 font-bold px-4 py-2 rounded-lg shadow-lg z-50";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2400);
}

// ===== 标签切换 =====
function showTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.add("hidden"));
  document.getElementById("tab-" + name).classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
}
document.querySelectorAll(".nav-btn").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));

// ===== 课程 =====
async function loadLessons() {
  const lessons = await fetch("/api/lessons").then(r => r.json());
  const wrap = document.getElementById("lessons-list");
  wrap.innerHTML = "";
  for (const L of lessons) {
    const done = state.done.includes(L.id);
    const card = document.createElement("div");
    card.className = "bg-slate-900 rounded-xl border " + (done ? "border-emerald-600" : "border-slate-800") + " p-5";
    card.innerHTML = `
      <div class="flex items-center gap-3 mb-2">
        <div class="text-2xl">${done ? "✅" : "📖"}</div>
        <div class="font-bold text-lg">第 ${L.id} 关 · ${L.title}</div>
        <div class="ml-auto text-xs bg-amber-500/20 text-amber-400 px-2 py-1 rounded-full">+${L.xp} XP</div>
      </div>
      <div class="text-slate-300 text-sm mb-4 leading-relaxed" style="white-space:pre-wrap">${mdLite(L.body)}</div>
      <div class="bg-slate-800/60 p-3 rounded-lg">
        <div class="font-bold text-sm mb-2">小测验：${L.quiz.q}</div>
        <div class="space-y-1" id="quiz-${L.id}">
          ${L.quiz.options.map((o, i) => `
            <button class="block w-full text-left px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm"
              onclick="answer(${L.id}, ${i}, ${L.quiz.answer}, ${L.xp})">${String.fromCharCode(65+i)}. ${o}</button>
          `).join("")}
        </div>
      </div>
    `;
    wrap.appendChild(card);
  }
}

function mdLite(s) {
  return s.replace(/\*\*(.+?)\*\*/g, '<b class="text-amber-400">$1</b>')
          .replace(/\n/g, "<br>");
}

window.answer = function(id, picked, correct, xp) {
  const wrap = document.getElementById("quiz-" + id);
  const btns = wrap.querySelectorAll("button");
  btns.forEach((b, i) => {
    b.disabled = true;
    if (i === correct) b.classList.add("bg-emerald-600");
    if (i === picked && i !== correct) b.classList.add("bg-rose-600");
  });
  if (picked === correct) {
    if (!state.done.includes(id)) {
      state.done.push(id);
      addXp(xp);
      toast(`✅ 答对！+${xp} XP`);
      setTimeout(loadLessons, 800);
    } else {
      toast("✅ 答对（已完成过）");
    }
  } else {
    toast("❌ 再想想~");
  }
};

// ===== 因子图鉴 =====
async function loadFactors() {
  const list = await fetch("/api/factors").then(r => r.json());
  state.factors = list;
  const grid = document.getElementById("factor-grid");
  grid.innerHTML = "";
  const colors = { "动量":"indigo", "反转":"rose", "波动":"sky", "技术":"emerald", "价值":"amber", "量价":"purple" };
  for (const f of list) {
    const c = colors[f.category] || "slate";
    const div = document.createElement("div");
    div.className = "card bg-slate-900 rounded-xl border border-slate-800 p-5";
    div.innerHTML = `
      <div class="flex items-center gap-2 mb-2">
        <div class="font-bold text-lg">${f.title}</div>
        <span class="text-xs px-2 py-0.5 rounded-full bg-${c}-500/20 text-${c}-300">${f.category}</span>
      </div>
      <div class="text-sm text-slate-300 mb-3">${f.story}</div>
      <div class="text-xs text-slate-500 mb-2">公式：\\(${f.formula}\\)</div>
      <div class="text-xs text-slate-400 italic mb-3">💡 ${f.intuition}</div>
      <button class="text-xs bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 rounded"
        onclick="jumpToLab('${f.key}')">⚗️ 在工坊里测一下 →</button>
    `;
    grid.appendChild(div);
  }
  if (window.MathJax) MathJax.typesetPromise();
  // 同时填实验室下拉
  const sel = document.getElementById("lab-factor");
  sel.innerHTML = list.map(f => `<option value="${f.key}">${f.title}（${f.category}）</option>`).join("");
}

window.jumpToLab = function(key) {
  document.getElementById("lab-factor").value = key;
  showTab("lab");
};

// ===== 术语表 =====
async function loadGlossary() {
  const list = await fetch("/api/glossary").then(r => r.json());
  const wrap = document.getElementById("glossary-list");
  wrap.innerHTML = list.map(g => `
    <div class="bg-slate-900 p-4 rounded-xl border border-slate-800">
      <div class="font-bold text-amber-400 mb-1">${g.term}</div>
      <div class="text-sm text-slate-300">${g.def}</div>
    </div>
  `).join("");
}

// ===== 实验室 =====
document.getElementById("run-btn").addEventListener("click", runLab);

async function runLab() {
  const btn = document.getElementById("run-btn");
  const status = document.getElementById("lab-status");
  btn.disabled = true;
  status.textContent = "⏳ 正在拉数据 + 计算因子 + 跑回测…首次调 A 股可能要等十几秒…";
  const body = {
    market: document.getElementById("lab-market").value,
    factor: document.getElementById("lab-factor").value,
    n_groups: parseInt(document.getElementById("lab-groups").value),
    hold: parseInt(document.getElementById("lab-hold").value),
    fwd: parseInt(document.getElementById("lab-fwd").value),
  };
  try {
    const r = await fetch("/api/compute", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    renderLab(data);
    addXp(5);
    status.textContent = "✅ 完成 (+5 XP)";
  } catch (e) {
    status.textContent = "❌ " + e.message;
  } finally {
    btn.disabled = false;
  }
}

function renderLab(d) {
  document.getElementById("lab-result").classList.remove("hidden");
  document.getElementById("r-title").textContent = d.meta.title + " · " + d.meta.category;
  document.getElementById("r-story").textContent = d.meta.story;
  document.getElementById("r-formula").innerHTML = "公式：\\(" + d.meta.formula + "\\)";
  if (window.MathJax) MathJax.typesetPromise();

  const fmt = (x, p=3) => (x == null || isNaN(x)) ? "—" : x.toFixed(p);
  const fmtPct = x => (x == null || isNaN(x)) ? "—" : (x * 100).toFixed(1) + "%";
  document.getElementById("s-icmean").textContent = fmt(d.ic_stats.mean, 4);
  document.getElementById("s-ir").textContent = fmt(d.ic_stats.ir);
  document.getElementById("s-win").textContent = fmtPct(d.ic_stats.win_rate);
  document.getElementById("s-n").textContent = d.ic_stats.n_periods;

  // 评判
  const v = document.getElementById("verdict");
  const ic = Math.abs(d.ic_stats.mean);
  let txt, cls;
  if (ic >= 0.05) { txt = "🌟 这是一个相当不错的因子！|IC| ≥ 0.05，在很多机构会作为正式 alpha 入库。"; cls = "border-emerald-600 bg-emerald-900/20"; }
  else if (ic >= 0.02) { txt = "👍 弱有效。单独用偏弱，但通常和其他因子合成。"; cls = "border-amber-600 bg-amber-900/20"; }
  else { txt = "🤷 在这个池子和时间段里几乎没有信息。换个市场/参数试试，或者它本来就不适合大盘股。"; cls = "border-rose-600 bg-rose-900/20"; }
  v.className = "p-4 rounded-xl border " + cls;
  v.textContent = txt;

  // 净值图
  const navTraces = [];
  const palette = ["#ef4444","#f97316","#eab308","#22c55e","#06b6d4","#6366f1","#a855f7","#ec4899"];
  let i = 0;
  for (const k of Object.keys(d.nav).filter(k => k !== "index")) {
    const isLs = k === "LongShort";
    navTraces.push({
      x: d.nav.index, y: d.nav[k], name: k, mode: "lines",
      line: { color: isLs ? "#fbbf24" : palette[i++ % palette.length], width: isLs ? 3 : 2, dash: isLs ? "dash" : "solid" }
    });
  }
  Plotly.newPlot("chart-nav", navTraces, {
    paper_bgcolor:"#0f172a", plot_bgcolor:"#0f172a",
    font:{color:"#cbd5e1"}, margin:{l:50,r:20,t:20,b:40},
    xaxis:{gridcolor:"#1e293b"}, yaxis:{gridcolor:"#1e293b", title:"净值"},
    legend:{orientation:"h"}
  }, {displayModeBar:false, responsive:true});

  // IC 图
  Plotly.newPlot("chart-ic", [{
    x: d.ic.index, y: d.ic.values, type:"bar",
    marker:{color: d.ic.values.map(v => v >= 0 ? "#22c55e" : "#ef4444")}
  }], {
    paper_bgcolor:"#0f172a", plot_bgcolor:"#0f172a",
    font:{color:"#cbd5e1"}, margin:{l:40,r:10,t:10,b:30},
    xaxis:{gridcolor:"#1e293b"}, yaxis:{gridcolor:"#1e293b"},
  }, {displayModeBar:false, responsive:true});

  // 分布
  Plotly.newPlot("chart-dist", [{
    x: d.distribution, type:"histogram", nbinsx: 50, marker:{color:"#8b5cf6"}
  }], {
    paper_bgcolor:"#0f172a", plot_bgcolor:"#0f172a",
    font:{color:"#cbd5e1"}, margin:{l:40,r:10,t:10,b:30},
    xaxis:{gridcolor:"#1e293b"}, yaxis:{gridcolor:"#1e293b"},
  }, {displayModeBar:false, responsive:true});

  // 快照
  const snap = document.getElementById("snapshot");
  const items = d.snapshot;
  const half = Math.ceil(items.length / 2);
  const top = items.slice(-half).reverse();
  const bot = items.slice(0, half);
  snap.innerHTML = `
    <div>
      <div class="font-bold text-emerald-400 mb-1">↑ 因子值最高（高分组 / 通常做多）</div>
      ${top.map(x => `<div class="flex justify-between border-b border-slate-800 py-1"><span>${x.ticker}</span><span class="text-emerald-300">${x.value.toFixed(4)}</span></div>`).join("")}
    </div>
    <div>
      <div class="font-bold text-rose-400 mb-1">↓ 因子值最低（低分组 / 通常做空）</div>
      ${bot.map(x => `<div class="flex justify-between border-b border-slate-800 py-1"><span>${x.ticker}</span><span class="text-rose-300">${x.value.toFixed(4)}</span></div>`).join("")}
    </div>
  `;
}

// ===== 启动 =====
showTab("home");
renderHud();
loadLessons();
loadFactors();
loadGlossary();
