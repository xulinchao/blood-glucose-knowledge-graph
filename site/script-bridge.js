/** 选题资料桥接 + 知识增强 + 成稿归档（浏览器端，规则对齐 script_knowledge.py） */
(function (global) {
  const DISCLAIMER =
    "以上为网上讨论/科普信息，个体情况请咨询医生，不构成医疗建议。";

  const CAT_MAP = {
    辟谣纠偏: "myth",
    饮食指南: "food",
    数字科普: "number",
    实操方法: "action",
    症状预警: "symptom",
    工具测评: "tool",
    案例故事: "story",
    避坑指南: "mistake",
  };

  let foodsCache = null;
  let knowledgeCache = null;
  let harvestCache = null;

  function norm(text) {
    return (text || "").replace(/\s+/g, "");
  }

  async function loadFoods() {
    if (foodsCache) return foodsCache;
    const res = await fetch("../data/foods/gi-database.json");
    if (!res.ok) throw new Error("gi-database load failed");
    const data = await res.json();
    foodsCache = data.foods || [];
    return foodsCache;
  }

  async function loadKnowledgeTopics() {
    if (knowledgeCache) return knowledgeCache;
    const res = await fetch("../data/knowledge/topics.json");
    if (!res.ok) throw new Error("topics load failed");
    const data = await res.json();
    knowledgeCache = data.topics || [];
    return knowledgeCache;
  }

  async function loadLatestHarvest() {
    if (harvestCache) return harvestCache;
    let pointer = null;
    try {
      const res = await fetch("../data/exports/latest-harvest.json");
      if (res.ok) pointer = await res.json();
    } catch (e) {
      /* ignore */
    }
    const path = pointer?.path
      ? `../data/exports/${pointer.path}`
      : `../data/exports/daily-harvest-${new Date().toISOString().slice(0, 10)}.json`;
    const res = await fetch(path);
    if (!res.ok) return null;
    harvestCache = await res.json();
    return harvestCache;
  }

  function foodVariants(name) {
    const out = [name];
    if (name.includes("/")) {
      name.split("/").forEach((p) => {
        if (p.trim()) out.push(p.trim());
      });
    }
    return out;
  }

  function matchFoods(text, foods, limit = 5) {
    const t = norm(text);
    const matched = [];
    foods.forEach((food) => {
      for (const v of foodVariants(food.name_zh || "")) {
        if (v.length >= 2 && t.includes(v)) {
          matched.push({ len: v.length, food });
          break;
        }
      }
    });
    matched.sort((a, b) => b.len - a.len);
    const seen = new Set();
    const out = [];
    matched.forEach(({ food }) => {
      if (seen.has(food.id)) return;
      seen.add(food.id);
      out.push(food);
    });
    return out.slice(0, limit);
  }

  function matchKnowledge(text, topics, limit = 3) {
    const t = norm(text);
    const scored = [];
    topics.forEach((topic) => {
      let score = 0;
      (topic.keywords || []).forEach((kw) => {
        if (kw && t.includes(kw)) score += kw.length;
      });
      const title = topic.title_zh || "";
      if (title && t.includes(norm(title.split("（")[0]))) score += 3;
      if (score) scored.push({ score, topic });
    });
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, limit).map((x) => x.topic);
  }

  function formatFoodFact(food) {
    const parts = [`${food.name_zh} GI${food.gi ?? "?"}`];
    if (food.gl_per_serving) parts.push(`GL${food.gl_per_serving}`);
    if (food.gi_level) parts.push(`${food.gi_level}GI`);
    return parts.join(" · ");
  }

  async function enrichDataRef(title, angle = "", snippet = "", extraLines = []) {
    const corpus = [title, angle, snippet].filter(Boolean).join(" ");
    const [foods, topics] = await Promise.all([loadFoods(), loadKnowledgeTopics()]);
    const matchedFoods = matchFoods(corpus, foods);
    const matchedTopics = matchKnowledge(corpus, topics);
    const lines = (extraLines || []).filter(Boolean).map((x) => x.trim());

    matchedFoods.forEach((food) => {
      const line = formatFoodFact(food);
      if (!lines.includes(line)) lines.push(line);
    });
    matchedTopics.forEach((topic) => {
      (topic.key_points || []).slice(0, 4).forEach((p) => {
        if (!lines.includes(p)) lines.push(p);
      });
    });
    if (snippet && snippet.trim() && !lines.some((l) => l.includes(snippet.slice(0, 20)))) {
      lines.push(`来源摘要：${snippet.trim().slice(0, 120)}`);
    }
    return {
      dataRef: lines,
      matchedFoods,
      matchedKnowledge: matchedTopics,
    };
  }

  function resolveWriteMode(useAs) {
    if (useAs === "hook_only") return "hook_only";
    if (useAs === "cite_directly") return "cite_directly";
    return "verify_before_script";
  }

  function buildVerifyChecklist(meta) {
    meta = meta || {};
    const useAs = meta.use_as || "verify_before_script";
    const tier = meta.evidence_tier || "D";
    const list = [
      { id: "disclaimer", text: "口播含「非医疗建议」声明", required: true, auto: true },
    ];
    if (useAs === "hook_only") {
      list.unshift({
        id: "hook_only",
        text: "正文仅写「大家在讨论…」，不得写成医学结论",
        required: true,
        auto: false,
      });
    }
    if (tier === "C" || tier === "D" || tier === "E" || useAs === "verify_before_script") {
      list.push({
        id: "verify_numbers",
        text: "关键数字/疗效已对照原帖或 A/B 级指南",
        required: true,
        auto: false,
      });
    }
    if (meta.source_urls && meta.source_urls.length) {
      list.push({
        id: "source_trace",
        text: "主张可追溯到来源链接",
        required: true,
        auto: false,
      });
    }
    if (meta.adversarial_flags && meta.adversarial_flags.length) {
      list.push({
        id: "adversarial",
        text: `已处理对抗性标记：${meta.adversarial_flags.join(", ")}`,
        required: true,
        auto: false,
      });
    }
    if (meta.creator_note) {
      list.push({ id: "creator_note", text: meta.creator_note, required: false, auto: false });
    }
    return list;
  }

  function harvestMetaFromTopic(topic) {
    const hm = topic.harvest_meta || {};
    const auth = hm.authenticity || {};
    return {
      use_as: hm.use_as || auth.use_as,
      evidence_tier: hm.evidence_tier || auth.evidence_tier,
      creator_note: hm.creator_note || auth.creator_note,
      adversarial_flags: auth.adversarial_flags || [],
      source_urls: topic.source_urls || [],
      topic_score: hm.topic_score,
    };
  }

  function harvestMetaFromItem(item) {
    const auth = item.authenticity || {};
    return {
      use_as: auth.use_as,
      evidence_tier: auth.evidence_tier,
      creator_note: auth.creator_note,
      adversarial_flags: auth.adversarial_flags || [],
      source_urls: item.url ? [item.url] : [],
      topic_score: item.topic_score,
      platform: item.platform,
      snippet: item.snippet || "",
    };
  }

  function findHarvestItem(harvest, { url, title }) {
    const items = harvest.items || [];
    if (url) {
      const hit = items.find((it) => it.url === url);
      if (hit) return hit;
    }
    if (title) {
      const key = norm(title);
      return items.find((it) => norm(it.title) === key);
    }
    return null;
  }

  function renderAuthenticityPanel(meta, container) {
    if (!container) return;
    const mode = resolveWriteMode(meta.use_as);
    const modeLabel = {
      hook_only: "仅讨论钩子",
      cite_directly: "可引用来源",
      verify_before_script: "写稿前核实",
    }[mode];
    const tier = meta.evidence_tier || "?";
    const sources = (meta.source_urls || [])
      .map(
        (u) =>
          `<a href="${u}" target="_blank" rel="noopener" style="color:var(--accent4);font-size:11px">${u.slice(0, 48)}…</a>`
      )
      .join("<br>");
    container.innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">
        <span class="auth-badge tier-${tier}">证据 ${tier}</span>
        <span class="auth-badge mode-${mode}">${modeLabel}</span>
        ${meta.topic_score != null ? `<span class="auth-badge">选题分 ${meta.topic_score}</span>` : ""}
      </div>
      ${meta.creator_note ? `<p style="font-size:12px;color:var(--muted);margin-bottom:6px">${meta.creator_note}</p>` : ""}
      ${sources ? `<div style="font-size:11px;color:var(--muted)">来源：<br>${sources}</div>` : ""}
    `;
  }

  function renderVerifyChecklist(checklist, container, checkedIds) {
    if (!container) return;
    checkedIds = checkedIds || new Set(["disclaimer"]);
    container.innerHTML = checklist
      .map((c) => {
        const checked = checkedIds.has(c.id) || c.auto ? "checked" : "";
        const req = c.required ? "必" : "选";
        return `<label class="verify-item"><input type="checkbox" data-verify-id="${c.id}" ${checked} ${c.auto ? "disabled" : ""}><span>[${req}] ${c.text}</span></label>`;
      })
      .join("");
  }

  const ARCHIVE_KEY = "bloodsugar_scripts";

  function loadLocalArchive() {
    try {
      return JSON.parse(localStorage.getItem(ARCHIVE_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveLocalArchive(records) {
    localStorage.setItem(ARCHIVE_KEY, JSON.stringify(records));
  }

  function saveScriptArchive(payload) {
    const records = loadLocalArchive();
    const id = `local-${Date.now()}`;
    const record = { id, created_at: new Date().toISOString(), ...payload };
    records.unshift(record);
    saveLocalArchive(records.slice(0, 100));
    return record;
  }

  function updateArchiveStatus(id, patch) {
    const records = loadLocalArchive();
    const idx = records.findIndex((r) => r.id === id);
    if (idx >= 0) {
      records[idx] = { ...records[idx], ...patch, updated_at: new Date().toISOString() };
      saveLocalArchive(records);
    }
    return records;
  }

  async function loadServerArchiveIndex() {
    try {
      const res = await fetch("../data/scripts/index.json");
      if (!res.ok) return [];
      const data = await res.json();
      return data.scripts || [];
    } catch (e) {
      return [];
    }
  }

  function maxPointsForDuration(duration) {
    if (duration <= 20) return 2;
    if (duration <= 45) return 3;
    if (duration <= 90) return 4;
    return 5;
  }

  function topicIntro(title, cat, writeMode) {
    const clean = (title || "").replace(/[？!！。]/g, "");
    if (writeMode === "hook_only" || !clean) return "";
    if (/怎么判断|如何判断|自测|有没有|是不是/.test(title)) {
      return `关于「${clean}」，先说明：网上的讨论和自测清单，只能帮你打开话题，不能替代体检和医生判断。`;
    }
    if (/能不能|可以吗|可不可以/.test(title)) {
      return `「${clean}」别只看一条短视频就下结论。下面把资料里相对好核查的几点，串成一条线。`;
    }
    if (cat === "myth") {
      return `围绕「${clean}」，咱们对照可查信息，把常见误会和相对靠谱的说法分开。`;
    }
    if (cat === "number") {
      return `「${clean}」涉及的数字不少，我按「先概念、再数字、再怎么用」来说。`;
    }
    return `围绕「${clean}」，我把资料里最关键、也相对好核对的几点，展开说人话版。`;
  }

  function expandPoint(point, index) {
    const leads = ["先说第一点，", "第二点，", "第三点，", "还有一点，", "最后补充，"];
    const lead = leads[index] || "另外，";
    let p = (point || "").trim();
    if (!p) return "";

    if p.startswith("【来源】") || p.startsWith("【来源】")) {
      const body = p.replace(/^【来源】/, "").trim();
      const sent = /[。！？]$/.test(body) ? body : `${body}。`;
      return `${lead}根据可查来源摘引：${sent}口播时请对照原链接核实，别当定论。`;
    }
    if (p.startsWith("来源摘要：")) {
      return `${lead}有来源提到：${p.slice(5)}。回原文核对前，别当定论传播。`;
    }
    if (/GI\s*\d|GL\s*\d|mmol|HbA1c|糖化|≤|≥/.test(p)) {
      return `${lead}数字这块：${p.replace(/[。．]$/, "")}。这是讨论用的参考，你的目标值以复查和医嘱为准。`;
    }
    if (/=|「|比喻|像.*一样|钥匙|锁/.test(p)) {
      const body = /[。！？]$/.test(p) ? p : `${p}。`;
      return `${lead}${body}这个比喻好懂，但别凭感觉就给自己贴标签。`;
    }
    if (/（[^）]+）/.test(p)) {
      const body = /[。！？]$/.test(p) ? p : `${p}。`;
      return `${lead}${body}`;
    }
    if (p.length <= 18) {
      return `${lead}很多人会提到：${p}。把它当成提问线索，不是结论。`;
    }
    return `${lead}${/[。！？]$/.test(p) ? p : `${p}。`}`;
  }

  function bodyBridge(topic, cat, writeMode) {
    if (writeMode === "hook_only") {
      return "如果你也有类似困惑，别自己吓自己，该复查就复查。";
    }
    if (/判断|自测|有没有|是否|怎么查/.test(topic || "")) {
      return "要是觉得对上了好几条，别自己诊断——空腹/餐后血糖、腰围、家族史，交给医生一起评估更靠谱。";
    }
    if (cat === "food") {
      return "记住：不是「绝对不能吃」，而是份量、搭配和烹饪方式一起考虑。";
    }
    if (cat === "number") {
      return "这些数字帮你建立语感，异常与否以化验单和医生解读为准。";
    }
    if (cat === "symptom") {
      return "症状只是提醒，不是确诊；有担心就尽快做正规检查。";
    }
    return "以上内容来自公开讨论和可查资料，怎么落到你身上，还要结合体检结果。";
  }

  function expandSpokenBody({ topic, cat, points, duration, writeMode }) {
    points = (points || []).filter(Boolean);
    if (writeMode === "hook_only") {
      const ps = points.length
        ? points.slice(0, maxPointsForDuration(duration))
        : ["有人在分享个人体验", "也有人在质疑夸张说法", "更稳妥的是结合体检和医嘱"];
      return `先把话说在前面：以下是网上讨论里反复出现的几点，不等于医学结论。\n\n${ps
        .map((p, i) => expandPoint(p, i))
        .join("\n\n")}\n\n${bodyBridge(topic, cat, writeMode)}`;
    }

    const limit = maxPointsForDuration(duration);
    const pts = points.slice(0, limit);
    if (!pts.length) {
      pts.push(
        "先搞清自己的体检指标，而不是只看短视频标题",
        "生活方式调整通常比极端做法更可坚持",
        "有用药或指标异常，及时咨询医生"
      );
    }

    const intro = topicIntro(topic, cat, writeMode);
    const expanded = pts.map((p, i) => expandPoint(p, i));
    const bridge = bodyBridge(topic, cat, writeMode);
    return [intro, ...expanded, bridge].filter(Boolean).join("\n\n");
  }

  function mergeSourceKeyPoints(dataRef, bundle) {
    const lines = [...(dataRef || [])];
    (bundle?.key_points || []).forEach((p) => {
      const line = p.startsWith("【来源】") ? p : `【来源】${p}`;
      if (!lines.includes(line)) lines.push(line);
    });
    return lines;
  }

  async function fetchSourceBundle(urls) {
    const list = (urls || []).filter(Boolean);
    if (!list.length) return null;
    const qs = list.map((u) => `url=${encodeURIComponent(u)}`).join("&");
    const res = await fetch(`/api/fetch-sources?${qs}`);
    if (!res.ok) {
      throw new Error(
        `拉取失败 (${res.status})。请用 python scripts/dev_server.py 8080 启动（不要用 python -m http.server）`
      );
    }
    return res.json();
  }

  function renderSourceFetchStatus(bundle, container) {
    if (!container) return;
    if (!bundle) {
      container.innerHTML =
        '<p style="font-size:12px;color:var(--muted)">有来源链接时可点「拉取来源字幕/正文」</p>';
      return;
    }
    const items = (bundle.items || [])
      .map((it) => {
        const st = it.status || (it.ok ? "ok" : "error");
        const n = (it.key_points || []).length;
        return `<div style="font-size:11px;margin-bottom:4px">• ${it.type || "?"} · ${st} · ${n} 条要点 ${it.note ? `<span style="color:var(--accent3)">— ${it.note}</span>` : ""}</div>`;
      })
      .join("");
    container.innerHTML = `<div style="font-size:12px;color:var(--accent);margin-bottom:6px">已拉取 ${bundle.key_points?.length || 0} 条来源要点</div>${items}`;
  }

  global.ScriptBridge = {
    DISCLAIMER,
    CAT_MAP,
    loadFoods,
    loadKnowledgeTopics,
    loadLatestHarvest,
    enrichDataRef,
    resolveWriteMode,
    buildVerifyChecklist,
    harvestMetaFromTopic,
    harvestMetaFromItem,
    findHarvestItem,
    renderAuthenticityPanel,
    renderVerifyChecklist,
    loadLocalArchive,
    saveScriptArchive,
    updateArchiveStatus,
    loadServerArchiveIndex,
    expandSpokenBody,
    fetchSourceBundle,
    mergeSourceKeyPoints,
    renderSourceFetchStatus,
  };
})(window);
