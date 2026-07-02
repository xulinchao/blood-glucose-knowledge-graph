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
  let briefCache = null;
  let discoveredCache = null;

  async function loadDiscoveredTopics() {
    if (discoveredCache) return discoveredCache;
    try {
      const res = await fetch("../data/discovered-topics.json");
      if (!res.ok) return { topics: [], archive: [] };
      const data = await res.json();
      discoveredCache = {
        topics: data.topics || [],
        archive: data.archive || [],
      };
    } catch (e) {
      discoveredCache = { topics: [], archive: [] };
    }
    return discoveredCache;
  }

  function findStoredDeepAnalysis(url, title) {
    if (!discoveredCache) return null;
    const all = [...(discoveredCache.topics || []), ...(discoveredCache.archive || [])];
    const norm = (s) => (s || "").trim();
    if (url) {
      const hit = all.find((t) => t.deep_analysis && (t.source_urls || []).some((u) => norm(u) === norm(url)));
      if (hit) return hit.deep_analysis;
    }
    if (title) {
      const hit = all.find((t) => t.deep_analysis && norm(t.title) === norm(title));
      if (hit) return hit.deep_analysis;
    }
    return null;
  }

  function buildClaimChecks(item) {
    const tier = item.evidence_tier || "?";
    const statusLabels = {
      pending_verify: "待核实",
      disputed: "存疑",
      exaggerated: "夸大",
      oversimplified: "过度简化",
      opinion: "观点",
    };
    const badgeStyle = {
      pending_verify: "background:rgba(255,217,61,0.15);color:#ffd93d",
      disputed: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      exaggerated: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      oversimplified: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      opinion: "background:rgba(108,140,255,0.15);color:#6c8cff",
      verified: "background:rgba(0,212,170,0.15);color:#00d4aa",
    };

    function inferHint(text, claimType) {
      if (/CGM|连续血糖|传感器|市场规模/i.test(text)) {
        return "查原始市场报告全文或 PubMed，核对口径与年份";
      }
      if (/CE|FDA|NMPA|获批|认证/i.test(text)) {
        return "可查欧盟 NANDO 或 FDA/NMPA 公示，区分临床试验与上市批准";
      }
      if (/\d+%|\d+亿|\d+[\d.]*万|CAGR/i.test(text)) {
        return "须找到原始出处（DOI/报告页），核对统计范围与时间";
      }
      if (claimType === "medication_claim" || claimType === "drug_discussion") {
        return "对照药品说明书；口播不得给出个体剂量";
      }
      if (/GI|升糖|粗粮|主食/i.test(text)) {
        return "前往 https://www.glycemicindex.com/ 核对具体品类";
      }
      if (/正常|算不算|诊断|空腹|糖化/i.test(text)) {
        return "对照《中国糖尿病防治指南》或 ADA 标准核对 cutoff 数值";
      }
      if (tier === "A" || tier === "B") {
        return "对照指南或原链接二次查证";
      }
      return "打开原贴核对，避免把讨论当医学结论";
    }

    function ruleStatus(c) {
      const ct = c.claim_type || "";
      const text = c.claim || "";
      if (ct === "food_cure_claim") return ["exaggerated", "食物疗效类断言，默认不可当事实"];
      if (ct === "causal_claim" && (tier === "D" || tier === "E" || tier === "?")) {
        return ["disputed", "因果/疗效断言来自低证据来源，宜改为「有人在讨论…」"];
      }
      if (ct === "medication_claim" || ct === "drug_discussion") {
        return ["pending_verify", "用药内容须遵医嘱"];
      }
      if (ct === "diagnostic_claim") return ["pending_verify", "诊断/标准类须对照最新指南"];
      if (ct === "numeric_claim" || /\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:亿|万)/.test(text)) {
        return ["pending_verify", "含具体数字，写稿前须回源"];
      }
      if (ct === "snippet_claim") return ["pending_verify", "摘要片段须与原视频/正文核对"];
      if (/百分百|所有|一定|根治|治愈|永不/.test(text)) return ["exaggerated", "含绝对化表述"];
      if (tier === "D" || tier === "E" || tier === "?") return ["opinion", "UGC 讨论，宜作话题钩子"];
      return ["pending_verify", "写稿前建议核对原贴与权威来源"];
    }

    const title = item.title || "";
    const snippet = item.snippet || "";
    const blob = `${title} ${snippet}`;
    let rawClaims = (item.claims || []).slice();
    const seenText = new Set();

    function addClaim(text, claimType) {
      const t = (text || "").trim();
      if (t.length < 6) return;
      const key = t.slice(0, 48);
      if (seenText.has(key)) return;
      seenText.add(key);
      rawClaims.push({ claim: t, claim_type: claimType || "topic_discussion", harm_risk: "low" });
    }

    if (!rawClaims.length) {
      title.split(/[？?；;，,]/).forEach((part) => addClaim(part.trim()));
      const numRe = /\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:亿|万)|GI\s*\d+|空腹\s*\d+(?:\.\d+)?|HbA1c\s*\d+(?:\.\d+)?/gi;
      let nm;
      while ((nm = numRe.exec(blob)) !== null) addClaim(nm[0], "numeric_claim");
      [
        [/(降血糖|降糖|控糖|逆转|治愈|根治)/i, "causal_claim"],
        [/(代替药物|停药|不用吃药|替换药物)/i, "medication_claim"],
        [/(二甲双胍|胰岛素|司美格鲁肽|格列|降糖药)/i, "drug_discussion"],
        [/(苹果醋|苦瓜|偏方|秘方)/i, "food_cure_claim"],
        [/(正常|多少|算不算|标准|诊断)/i, "diagnostic_claim"],
      ].forEach(([re, ct]) => {
        const m = blob.match(re);
        if (m) addClaim(m[0], ct);
      });
      if (!seenText.size) addClaim(title || snippet.slice(0, 80));
    }

    const sn = snippet.trim();
    if (sn.length > 20) {
      for (const sent of sn.split(/[。！!；;]/)) {
        const s = sent.trim();
        if (s.length >= 12) {
          addClaim(s.slice(0, 120), "snippet_claim");
          break;
        }
      }
    }

    return rawClaims.slice(0, 6).map((c) => {
      if (!c || !c.claim) return null;
      const [status, note] = ruleStatus(c);
      return {
        text: c.claim,
        status,
        status_label: statusLabels[status] || status,
        note,
        verify_hint: inferHint(c.claim, c.claim_type || ""),
        _badgeStyle: badgeStyle[status] || badgeStyle.pending_verify,
      };
    }).filter(Boolean);
  }

  function buildDeepAnalysisFromBriefItem(item) {
    const gate = item.gate || item.writing_safety || {};
    const editorial = item.editorial || {};
    const cc = item.cognitive_conflict || {};
    const tier = item.evidence_tier || "?";
    const useAs = gate.use_as || item.use_as || "";
    const useLabels = {
      cite_directly: "可引用",
      verify_before_script: "写稿前核实",
      hook_only: "仅钩子",
      safe_to_discuss: "可讨论",
    };
    const tierReason =
      editorial.why_selected ||
      {
        A: "一级权威来源",
        B: "专业平台来源，须回源核实",
        C: "作者有医疗相关标识，仍须核对资质",
      }[tier] ||
      "UGC 讨论热点，默认不可当医学结论";
    const passed = gate.passed || gate.gate_passed;
    const credibility = `${tier}级 · ${useLabels[useAs] || useAs || "—"} · ${
      passed ? "Gate 可写" : "不可当医学结论"
    } — ${tierReason}`;

    const steps = [];
    if (item.url) steps.push(`打开原贴核对标题与摘要主张：${item.url}`);
    if (item.author) steps.push(`核实作者/机构资质：${item.author}`);
    const corpus = [item.title, item.category, item.snippet].filter(Boolean).join(" ");
    if (/GI|粗粮|主食|食物|饮食|水果|零食/i.test(corpus)) {
      steps.push("若涉及 GI/食物数据：前往 https://www.glycemicindex.com/ 核对具体品类");
    }
    if (useAs === "verify_before_script" || useAs === "cite_directly" || tier === "A" || tier === "B") {
      steps.push("关键数字对照《中国糖尿病防治指南》或 nhc.gov.cn 等权威来源");
    }
    const forbidden = gate.forbidden_expressions || [];
    if (forbidden.length) steps.push("写稿避免：" + forbidden.slice(0, 4).join("、"));
    if (item.creator_note) steps.push(item.creator_note);
    steps.push("口播结尾须含非医疗建议声明（个体情况请咨询医生）");

    const keyPoints = [];
    (item.claims || []).slice(0, 4).forEach((c) => {
      if (c && c.claim) keyPoints.push(c.claim);
    });
    if (!keyPoints.length && cc.claim_summary) keyPoints.push(cc.claim_summary);
    if (editorial.misleading_risk) keyPoints.push("误导风险：" + editorial.misleading_risk);

    let hook = editorial.safe_rewrite || cc.controversy_hint || "";
    if (!hook) hook = `网上有人在聊「${(item.title || "").slice(0, 36)}…」`;

    let caution = editorial.misleading_risk || "";
    const hedges = gate.required_hedges || [];
    if (hedges.length) caution = (caution ? caution + "；" : "") + "须加缓冲：" + hedges.join("、");
    if (!caution) caution = "个体情况差异大，不构成医疗建议；涉及用药须遵医嘱。";

    const prop = item.propagation || {};
    const heat = item.heat_score ?? prop.heat_score;
    let trend = item.platform_label || item.platform || "";
    if (heat != null) trend = (trend ? trend + " · " : "") + `热度 ${heat}`;
    if (prop.engagement) trend += `，互动约 ${prop.engagement}`;

    return {
      credibility,
      claim_checks: buildClaimChecks(item),
      verification_steps: steps,
      script_angles: { hook, key_points: keyPoints, caution },
      trend_context: trend,
      _source: "rule_engine",
      _ai: false,
    };
  }

  function mergeClaimChecks(ruleChecks, storedChecks) {
    if (!storedChecks || !storedChecks.length) return ruleChecks || [];
    if (!ruleChecks || !ruleChecks.length) return storedChecks;
    const out = [];
    const used = new Set();
    storedChecks.forEach((sc) => {
      out.push(sc);
      used.add((sc.text || "").slice(0, 40));
    });
    ruleChecks.forEach((rc) => {
      const key = (rc.text || "").slice(0, 40);
      if (!used.has(key)) out.push(rc);
    });
    return out.slice(0, 8);
  }

  async function resolveDeepAnalysis(item) {
    await loadDiscoveredTopics();
    const stored = findStoredDeepAnalysis(item.url, item.title);
    const rule = buildDeepAnalysisFromBriefItem(item);
    if (stored && stored._source !== "rule_engine") {
      return {
        ...rule,
        ...stored,
        claim_checks: mergeClaimChecks(rule.claim_checks, stored.claim_checks),
        script_angles: { ...rule.script_angles, ...(stored.script_angles || {}) },
        _source: stored._source || "agent_or_manual",
        _ai: stored._ai !== false,
      };
    }
    if (stored && stored.claim_checks && stored.claim_checks.length) {
      return {
        ...rule,
        claim_checks: mergeClaimChecks(rule.claim_checks, stored.claim_checks),
        _source: "agent_or_manual",
        _ai: false,
      };
    }
    return rule;
  }

  function escModal(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function claimBadgeStyle(status) {
    const map = {
      pending_verify: "background:rgba(255,217,61,0.15);color:#ffd93d",
      disputed: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      exaggerated: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      oversimplified: "background:rgba(255,107,107,0.12);color:#ff6b6b",
      opinion: "background:rgba(108,140,255,0.15);color:#6c8cff",
      verified: "background:rgba(0,212,170,0.15);color:#00d4aa",
    };
    return map[status] || map.pending_verify;
  }

  function toSourcePreview(result) {
    if (!result || !result.ok) {
      return {
        status: "error",
        url: (result && result.url) || "",
        error: (result && result.error) || "拉取失败",
      };
    }
    const excerptParts = [];
    if (result.transcript) excerptParts.push(String(result.transcript).slice(0, 1200));
    else if (result.description) excerptParts.push(String(result.description).slice(0, 800));
    else if (result.raw_text) excerptParts.push(String(result.raw_text).slice(0, 1200));
    return {
      content_status: result.content_status || result.status || "ok",
      type: result.type || "",
      url: result.url || "",
      title: result.title || "",
      author: result.author || "",
      excerpt: excerptParts.join("\n\n").slice(0, 1500),
      key_points: (result.key_points || []).slice(0, 8),
      sources_used: result.sources_used || [],
      note: result.note || "",
      fetched_at: result.fetched_at || "",
    };
  }

  function renderSourcePreviewHtml(preview, url) {
    if (!preview) {
      return url
        ? '<div id="source-preview-host" style="font-size:12px;color:#8b919a">正在拉取原贴字幕/正文…</div>'
        : "";
    }
    if (preview.status === "error") {
      return `<div style="margin-bottom:14px;padding:12px;background:#1a1d24;border:1px solid #2a2f3a;border-radius:8px">
        <div style="font-size:12px;font-weight:600;color:#ff6b6b;margin-bottom:6px">📄 原贴内容未拉取</div>
        <div style="font-size:11px;color:#8b919a">${escModal(preview.error || "请用 dev_server 或重新跑采集")}</div>
        ${url ? `<div style="margin-top:8px"><a href="${escModal(url)}" target="_blank" rel="noopener" style="color:#6c8cff;font-size:11px">打开原贴 →</a></div>` : ""}
      </div>`;
    }
    const kps = preview.key_points || [];
    const excerpt = (preview.excerpt || "").trim();
    const note = preview.note || "";
    const src = (preview.sources_used || []).join("、");
    const kpHtml = kps.length
      ? `<ul style="margin:8px 0 0 18px;padding:0;line-height:1.55;color:#c9cdd4">${kps
          .map((p) => `<li>${escModal(String(p).slice(0, 140))}</li>`)
          .join("")}</ul>`
      : "";
    const exHtml =
      excerpt.length > 40
        ? `<pre style="font-size:11px;white-space:pre-wrap;margin:8px 0 0;color:#8b919a;max-height:160px;overflow:auto">${escModal(excerpt.slice(0, 800))}${excerpt.length > 800 ? "…" : ""}</pre>`
        : "";
    if (!kpHtml && !exHtml) {
      return `<div id="source-preview-host" style="margin-bottom:14px;padding:12px;background:#1a1d24;border:1px solid #2a2f3a;border-radius:8px">
        <div style="font-size:12px;font-weight:600;color:#ffd93d">📄 原贴暂无字幕/正文</div>
        <div style="font-size:11px;color:#8b919a;margin-top:6px">仅有标题可用；B站无 CC 时须点开视频核对，或本地用 dev_server 重新拉取。</div>
        ${url ? `<a href="${escModal(url)}" target="_blank" rel="noopener" style="color:#6c8cff;font-size:11px;margin-top:8px;display:inline-block">打开原贴 →</a>` : ""}
      </div>`;
    }
    return `<div id="source-preview-host" style="margin-bottom:14px;padding:12px;background:#1a1d24;border:1px solid rgba(108,140,255,.25);border-radius:8px">
      <div style="font-size:12px;font-weight:600;color:#6c8cff;margin-bottom:4px">📄 原贴内容摘要</div>
      ${preview.author ? `<div style="font-size:11px;color:#8b919a">作者：${escModal(preview.author)} · ${escModal(preview.type || "")} · ${escModal(preview.status || "")}</div>` : ""}
      ${kpHtml}
      ${exHtml}
      ${note ? `<div style="font-size:11px;color:#ffd93d;margin-top:8px">${escModal(note)}</div>` : ""}
      ${src ? `<div style="font-size:10px;color:#8b919a;margin-top:4px">抓取：${escModal(src)}</div>` : ""}
      ${url ? `<a href="${escModal(url)}" target="_blank" rel="noopener" style="color:#6c8cff;font-size:11px;margin-top:8px;display:inline-block">打开原贴核对 →</a>` : ""}
    </div>`;
  }

  function renderDeepAnalysisModalHtml(title, analysis, sourcePreview, url) {
    const da = analysis || {};
    const sa = da.script_angles || {};
    const isRule = da._source === "rule_engine";
    const badge = isRule
      ? '<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(255,217,61,0.15);color:#ffd93d">规则解读 · 无 AI · 不标「已核实」</span>'
      : '<span style="font-size:10px;padding:2px 8px;border-radius:4px;background:rgba(0,212,170,0.15);color:#00d4aa">Agent/人工增强</span>';
    const sourceHtml = renderSourcePreviewHtml(sourcePreview, url);
    const claimHtml = (da.claim_checks || [])
      .map((c) => {
        const st = claimBadgeStyle(c.status);
        return `<li style="margin-bottom:10px;line-height:1.55">
          <span>${escModal(c.text)}</span>
          <span style="font-size:10px;font-weight:700;padding:1px 7px;border-radius:4px;margin-left:6px;${st}">${escModal(c.status_label || c.status)}</span>
          ${c.note ? `<div style="font-size:11px;color:var(--muted);margin-top:4px">${escModal(c.note)}</div>` : ""}
          ${c.verify_hint ? `<div style="font-size:11px;color:var(--accent4);margin-top:3px">🔍 ${escModal(c.verify_hint)}</div>` : ""}
        </li>`;
      })
      .join("");
    const steps = (da.verification_steps || [])
      .map((s) => `<li>${escModal(s)}</li>`)
      .join("");
    const points = (sa.key_points || [])
      .map((p) => `<li>${escModal(p)}</li>`)
      .join("");
    return `
      <div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:999;display:flex;align-items:center;justify-content:center" id="deep-analysis-overlay">
        <div style="background:var(--bg);border:1px solid var(--rule);border-radius:12px;max-width:600px;width:92%;max-height:85vh;overflow:auto;padding:20px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:12px">
            <div>
              <h3 style="font-size:15px;margin:0 0 6px;line-height:1.45">${escModal(title)}</h3>
              ${badge}
            </div>
            <button type="button" id="deep-analysis-close-btn" style="background:none;border:none;color:#8b919a;cursor:pointer;font-size:18px">×</button>
          </div>
          ${sourceHtml}
          ${da.credibility ? `<div style="margin-bottom:12px"><span style="font-size:11px;color:#8b919a">整体可信度</span><div style="font-size:13px;margin-top:4px;line-height:1.6;color:#c9cdd4">${escModal(da.credibility)}</div></div>` : ""}
          ${claimHtml ? `<div style="margin-bottom:14px;padding:12px;background:#1a1d24;border:1px solid #2a2f3a;border-radius:8px"><span style="font-size:12px;font-weight:600;color:#e8eaed">📋 原贴内容主张核验</span><ul style="font-size:12px;margin:8px 0 0;padding-left:18px;list-style:disc;color:#c9cdd4">${claimHtml}</ul></div>` : ""}
          ${steps ? `<div style="margin-bottom:12px"><span style="font-size:11px;color:#8b919a">自行检索建议（通用）</span><ul style="font-size:12px;margin:4px 0 0 16px;line-height:1.6;color:#c9cdd4">${steps}</ul></div>` : ""}
          ${sa.hook || points || sa.caution ? `<div style="margin-bottom:12px"><span style="font-size:11px;color:var(--muted)">脚本建议</span>
            ${sa.hook ? `<div style="font-size:12px;margin-top:4px"><strong>Hook:</strong> ${escModal(sa.hook)}</div>` : ""}
            ${points ? `<div style="font-size:12px;margin-top:4px"><strong>要点:</strong><ul style="margin:4px 0 0 16px">${points}</ul></div>` : ""}
            ${sa.caution ? `<div style="font-size:12px;margin-top:4px;color:var(--accent2)"><strong>注意:</strong> ${escModal(sa.caution)}</div>` : ""}
          </div>` : ""}
          ${da.trend_context ? `<div style="margin-bottom:12px"><span style="font-size:11px;color:var(--muted)">趋势背景</span><div style="font-size:12px;margin-top:4px">${escModal(da.trend_context)}</div></div>` : ""}
          <div style="text-align:right;margin-top:12px">
            <button type="button" id="deep-analysis-fill-btn" style="padding:6px 14px;border-radius:6px;border:none;background:var(--accent);color:var(--bg);cursor:pointer;font-size:12px">填入写稿</button>
          </div>
        </div>
      </div>`;
  }


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

  async function loadLatestBrief() {
    if (briefCache) return briefCache;
    let pointer = null;
    try {
      const res = await fetch("../data/exports/latest-brief.json");
      if (res.ok) pointer = await res.json();
    } catch (e) {
      /* ignore */
    }
    const path = pointer?.path
      ? `../data/exports/${pointer.path}`
      : `../data/exports/daily-brief-${new Date().toISOString().slice(0, 10)}.json`;
    const res = await fetch(path);
    if (!res.ok) return null;
    briefCache = await res.json();
    return briefCache;
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
    const gate = item.gate || {};
    return {
      use_as: gate.use_as || auth.use_as,
      evidence_tier: auth.evidence_tier,
      creator_note: gate.creator_note || auth.creator_note,
      adversarial_flags: auth.adversarial_flags || [],
      source_urls: item.url ? [item.url] : [],
      topic_score: item.writability_score || item.topic_score,
      writability_score: item.writability_score || item.topic_score,
      heat_score: item.heat_score,
      platform: item.platform,
      snippet: item.snippet || "",
      gate: gate,
      allowed_frame: gate.allowed_frame,
      forbidden_expressions: gate.forbidden_expressions || [],
      required_hedges: gate.required_hedges || [],
      claims: item.claims || [],
    };
  }

  const FORBIDDEN_PATTERNS = [
    [/一定能(降|控制)?糖/gi, "绝对化疗效"],
    [/可以降血糖/gi, "因果疗效断言"],
    [/保证(逆转|治愈|根治)/gi, "治愈承诺"],
    [/所有人都/gi, "绝对化人群"],
    [/替医嘱|代替医生/gi, "替代就医"],
    [/停药|不用吃药/gi, "用药建议"],
    [/研究表明你一定/gi, "UGC 确定性断言"],
    [/只要.{0,8}就能(降|治)/gi, "因果跳跃"],
  ];

  const CAUSAL_JUMP_PATTERNS = [
    [/因为.{2,30}所以.{0,12}(降|控)糖/gi, "因果跳跃"],
    [/吃了.{2,20}(血糖|降糖)/gi, "因果跳跃"],
  ];

  const DEFAULT_HEDGES = ["目前证据有限", "个体差异较大", "请以复查和医嘱为准"];

  function lintScriptText(text, meta, writeMode) {
    meta = meta || {};
    writeMode = writeMode || "verify_before_script";
    const violations = [];
    const suggestions = [];
    const blob = text || "";

    FORBIDDEN_PATTERNS.forEach(([re, label]) => {
      if (re.test(blob)) violations.push({ type: "forbidden_pattern", label });
    });
    CAUSAL_JUMP_PATTERNS.forEach(([re, label]) => {
      if (re.test(blob)) violations.push({ type: "causal_jump", label });
    });

    const tier = meta.evidence_tier || "D";
    const frame = meta.allowed_frame || (meta.gate && meta.gate.allowed_frame) || "";
    const hedges = meta.required_hedges || (meta.gate && meta.gate.required_hedges) || DEFAULT_HEDGES;
    const needsHedge =
      writeMode === "hook_only" || tier === "D" || tier === "E" || frame === "discussion_only";
    if (needsHedge && hedges.length && !hedges.some((h) => blob.includes(h))) {
      violations.push({ type: "missing_hedge", label: "缺少非确定性降权表述" });
      suggestions.push(`建议加入：「${hedges[0]}」`);
    }

    const forbidden =
      meta.forbidden_expressions || (meta.gate && meta.gate.forbidden_expressions) || [];
    forbidden.forEach((expr) => {
      if (expr && blob.includes(expr)) {
        violations.push({ type: "gate_forbidden", label: `含 Gate 禁止表达「${expr}」` });
      }
    });

    const disclaimerMarkers = ["不构成医疗建议", "咨询医生", "非医疗建议", "遵医嘱"];
    if (!disclaimerMarkers.some((m) => blob.includes(m))) {
      violations.push({ type: "missing_disclaimer", label: "缺少医疗免责声明" });
    }

    return { passed: violations.length === 0, violations, suggestions };
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
    if (cat === "food") {
      return `说到「${clean}」，很多人的第一反应和实际情况可能差挺远。`;
    }
    if (cat === "action") {
      return `「${clean}」其实没多复杂，关键就那几步，我一个个拆开。`;
    }
    if (cat === "symptom") {
      return `「${clean}」——这些信号容易被忽略，也可能是身体在提醒你。`;
    }
    return `围绕「${clean}」，我把资料里最关键、也相对好核对的几点，展开说人话版。`;
  }

  function expandPoint(point, index) {
    let p = (point || "").trim();
    if (!p) return "";

    if (p.startsWith("【来源】")) {
      const body = p.replace(/^【来源】/, "").trim();
      const sent = /[。！？]$/.test(body) ? body : `${body}。`;
      return `根据可查来源摘引：${sent}口播时请对照原链接核实，别当定论。`;
    }
    if (p.startsWith("来源摘要：")) {
      return `有来源提到：${p.slice(5)}。回原文核对前，别当定论传播。`;
    }
    if (/GI\s*\d|GL\s*\d|mmol|HbA1c|糖化|≤|≥/.test(p)) {
      return `数字这块：${p.replace(/[。．]$/, "")}。这是讨论用的参考，你的目标值以复查和医嘱为准。`;
    }
    if (/=|「|比喻|像.*一样|钥匙|锁/.test(p)) {
      const body = /[。！？]$/.test(p) ? p : `${p}。`;
      return `${body}这个比喻好懂，但别凭感觉就给自己贴标签。`;
    }
    if (p.length <= 18) {
      return `${p}。很多人会提到这一点，把它当成提问线索就好。`;
    }
    return `${/[。！？]$/.test(p) ? p : `${p}。`}`;
  }

  function bodyBridge(topic, cat, writeMode) {
    if (writeMode === "hook_only") {
      return "如果你也有类似困惑，别自己吓自己，该复查就复查。";
    }
    if (/判断|自测|有没有|是否|怎么查/.test(topic || "")) {
      return "要是觉得对上了好几条，别自己诊断——空腹/餐后血糖、腰围、家族史，交给医生一起评估更靠谱。";
    }
    if (cat === "food") {
      return "不是「绝对不能吃」，份量、搭配、烹饪方式一起考虑，比刻意忌口有效得多。";
    }
    if (cat === "number") {
      return "这些数字帮你建立语感，异常与否以化验单和医生解读为准，别拿着短视频当诊断书。";
    }
    if (cat === "symptom") {
      return "症状只是提醒，不是确诊；有担心就尽快做正规检查，别拖。";
    }
    if (cat === "action") {
      return "这几个动作不花钱、不费事，难的是坚持。从今天开始，比从明天开始强。";
    }
    if (cat === "tool") {
      return "选工具看自身需求，没有「最好」，只有「最适合你」。";
    }
    if (cat === "myth") {
      return "记住：常识不一定对，数据不一定全，有问题就问医生。";
    }
    return "以上来自公开讨论和可查资料，怎么落到你身上，还要结合体检结果。";
  }

  /* ── STEPPS: 诱因锚定（Triggers） ── */
  function triggerAnchor(cat) {
    const anchors = {
      food: [
        "你打开外卖App的时候注意过吗？",
        "超市货架第二排，那些看着健康的，你仔细看过配料表吗？",
        "你上次吃完饭困得不行，有没有想过其实跟这有关？",
        "打开冰箱看看，你家常备的那几样，可能就有雷。"
      ],
      number: [
        "体检报告上那几个数字，你真的看懂了吗？",
        "你天天测的那个数字，到底多少算正常？",
        "上次复查拿到的单子，你是扫了一眼就塞抽屉了吗？",
        "你手机里的健康App，上面那个数字你信吗？"
      ],
      myth: [
        "你转发到家人群的那条，可能就是错的。",
        "上次有人跟你说「这个能降糖」，你信了吗？",
        "朋友圈那个「控糖秘诀」，转发之前先想想。",
        "你妈发给你的那条养生链接，先别急着信。"
      ],
      action: [
        "吃完饭你一般做什么？躺下刷手机？",
        "你每天那几个习惯，可能正在悄悄帮你——也可能在害你。",
        "其实不用花大钱，几个小动作就能改变不少。",
        "你有没有觉得，坚持什么最难？"
      ],
      symptom: [
        "你最近有没有觉得——说不上哪里不对，就是不太对劲？",
        "有些信号你每天都在经历，但从来没当回事。",
        "你有没有吃完饭就犯困、口干、怎么喝水都不解渴？",
        "你身边有没有人，明明不胖但体检指标不好？"
      ],
      tool: [
        "你手机里装了几个健康App？有几个是认真在用的？",
        "你花在控糖上的冤枉钱，可能够买一台好血糖仪了。",
        "测评了好几款，有些好评如潮的，实际也就那样。",
        "选工具这件事，贵的和好用的是两回事。"
      ],
      story: [
        "你身边有没有这样的人——看起来挺健康，结果突然查出来？",
        "我认识一个人，跟你我差不多，后来发生的事让他彻底改变了。",
        "有些事情，不发生在自己身上，你永远不会当回事。"
      ],
      mistake: [
        "你踩过的坑，可能很多人都踩过——但没人告诉你原因。",
        "你是不是也觉得控糖就是不吃主食？那你可能从起点就走偏了。",
        "有些「常识」，做了反而更糟。"
      ]
    };
    const pool = anchors[cat] || anchors.food;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  /* ── STEPPS: 微叙事包装（Story） ── */
  function microNarrative(cat, topic) {
    const narratives = {
      food: [
        (t) => `说实话，以前我也不信${t.replace(/[？?。.]/g, "")}这事。直到有一次我自己测了一下餐后血糖，数字吓了我一跳——从那以后我开始认真查每样东西的GI值。`,
        (t) => `我身边一个朋友，控糖半年了，自认为吃得挺健康。结果有一天我们聊起来，发现他一直在踩雷——今天就把他踩过的几个坑摊开讲。`
      ],
      number: [
        (t) => `拿到体检报告那天，我看到那个数字，第一反应是「不可能吧」。后来才知道，大部分人第一次看到这个数字，反应都一样——但你越早搞明白它，越好办。`,
        (t) => `你有没有这种经历：医生说了个数字，你点头说知道了，回家一查发现完全不是自己理解的意思。今天就把这几个最容易搞混的数字讲清楚。`
      ],
      myth: [
        (t) => `我妈前阵子转发给我一篇文章，标题写得特别吓人。我一看内容，好几条都是误导。这种情况太常见了——今天我就把最典型的几个拆开。`,
        (t) => `之前我也信过${t.replace(/[？?。.]/g, "")}。后来自己查了资料才发现，真相和网上传的差太远了。今天帮你省去这个弯路。`
      ],
      action: [
        (t) => `刚开始控糖那会儿，我觉得特别难——什么都要记、什么都要算。后来发现，其实就那几件事最关键。做对了，其他自然跟着变。`,
        (t) => `有个粉丝私信我说，控糖三个月瘦了10斤，但方法特别简单。我让他把每天做的事情列了一下，发现就那几步。今天拆开讲。`
      ],
      symptom: [
        (t) => `我之前也不知道这些是信号。直到身边有人因为这些「小毛病」去检查，才发现问题没那么简单。今天就把这几个容易被忽略的信号列出来。`,
        (t) => `有些人天天觉得累、口干、吃完就困，但从来没想过这些可能有关联。不是说一定有问题，但知道了至少能多留个心眼。`
      ],
      tool: [
        (t) => `我自己买过不下五款控糖相关的东西，有些是真有用，有些纯粹智商税。今天把买过的、测过的摊开讲。`,
        (t) => `你有没有这种体验——看了测评买的，到手发现根本不是那么回事？测评太多了反而不知道该信谁。今天我自己测过的几款拿出来对比。`
      ]
    };
    const pool = narratives[cat] || narratives.food;
    return pool[Math.floor(Math.random() * pool.length)](topic);
  }

  function hasSubstantiveSourceLines(lines) {
    return (lines || []).some((line) => {
      const t = String(line || "").trim();
      if (!t || t.startsWith("来源视频标题：")) return false;
      if (t.startsWith("【来源】")) {
        const body = t.replace(/^【来源】/, "").trim();
        if (body.startsWith("来源视频标题：")) return false;
        return body.length >= 12;
      }
      if (t.startsWith("来源摘要：") && t.length > 18) return true;
      if (/GI\s*\d|GL\s*\d|mmol|HbA1c|糖化/.test(t)) return true;
      return t.length >= 20;
    });
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
      return (
        "⚠️ 本条暂无原贴正文。请先点「拉取原贴」（需 dev_server）或 B 站无字幕时用 bili audio + agent-reach transcribe。\n\n" +
        "缺少正文请勿直接发布——复制 AI Prompt 人工写稿更稳妥。"
      );
    }
    if (!hasSubstantiveSourceLines(points)) {
      return (
        "⚠️ 目前只有标题/标签，没有视频字幕或正文摘要。\n\n" +
        pts.slice(0, 2).map((p, i) => expandPoint(p, i)).join("\n\n") +
        "\n\n（以上为资料库自动匹配，非原贴逐字稿；写稿前须拉取原贴或转写视频。）"
      );
    }

    const intro = topicIntro(topic, cat, writeMode);
    const narrative = microNarrative(cat, topic);
    const expanded = pts.map((p, i) => expandPoint(p, i));
    const bridge = bodyBridge(topic, cat, writeMode);
    return [intro, narrative, ...expanded, bridge].filter(Boolean).join("\n\n");
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
    try {
      const res = await fetch(`/api/fetch-sources?${qs}`);
      if (res.ok) return res.json();
      if (res.status === 404) {
        /* dev_server 未启动，尝试逐个加载本地 source-cache */
        const items = [];
        for (const url of list) {
          const hash = await simpleHash(url);
          try {
            const cr = await fetch(`../data/source-cache/${hash}.json`);
            if (cr.ok) {
              items.push(await cr.json());
              continue;
            }
          } catch (_) { /* ignore */ }
          items.push({ ok: false, url, status: "no_server", type: "skip", key_points: [], note: "无 dev_server 且无本地缓存" });
        }
        const kp = items.flatMap((it) => it.key_points || []);
        return { ok: kp.length > 0, items, key_points: kp, errors: [], note: "dev_server 未启动，已从本地缓存加载（可能不是最新）" };
      }
      throw new Error(`拉取失败 (${res.status})`);
    } catch (e) {
      if (e.message && e.message.includes("Failed to fetch")) {
        /* file:// 协议或网络不可用，返回降级标记 */
        return { ok: false, items: list.map((url) => ({ ok: false, url, status: "offline", type: "skip", key_points: [], note: "离线模式" })), key_points: [], errors: [], note: "离线模式：使用已有数据点生成文案" };
      }
      throw e;
    }
  }

  async function simpleHash(str) {
    /* SHA-256 前16位，与 source_fetcher.url_cache_key 一致 */
    if (crypto.subtle) {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
      return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
    }
    /* 极端降级：用简单 hash（不保证一致） */
    let h = 0;
    for (let i = 0; i < str.length; i++) { h = ((h << 5) - h + str.charCodeAt(i)) | 0; }
    return Math.abs(h).toString(16).padStart(16, "0");
  }

  function renderSourceFetchStatus(bundle, container) {
    if (!container) return;
    if (!bundle) {
      container.innerHTML =
        '<p style="font-size:12px;color:var(--muted)">有来源链接时可点「拉取来源字幕/正文」</p>';
      return;
    }
    const noteHtml = bundle.note
      ? `<div style="font-size:11px;color:var(--accent3);margin-bottom:4px">${bundle.note}</div>`
      : "";
    const items = (bundle.items || [])
      .map((it) => {
        const st = it.status || (it.ok ? "ok" : "error");
        const n = (it.key_points || []).length;
        const color = st === "ok" ? "var(--accent)" : st === "offline" || st === "no_server" ? "var(--muted)" : "var(--accent2)";
        return `<div style="font-size:11px;margin-bottom:4px;color:${color}">• ${it.type || "?"} · ${st} · ${n} 条要点${it.note ? ` — ${it.note}` : ""}</div>`;
      })
      .join("");
    const kpCount = bundle.key_points?.length || 0;
    const kpColor = kpCount > 0 ? "var(--accent)" : "var(--muted)";
    container.innerHTML = `<div style="font-size:12px;color:${kpColor};margin-bottom:6px">${kpCount > 0 ? `已加载 ${kpCount} 条来源要点` : "来源资料未拉取，文案将基于已有数据点生成"}</div>${noteHtml}${items}`;
  }

  global.ScriptBridge = {
    DISCLAIMER,
    CAT_MAP,
    loadFoods,
    loadKnowledgeTopics,
    loadLatestHarvest,
    loadLatestBrief,
    loadDiscoveredTopics,
    buildDeepAnalysisFromBriefItem,
    buildClaimChecks,
    toSourcePreview,
    renderSourcePreviewHtml,
    resolveDeepAnalysis,
    renderDeepAnalysisModalHtml,
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
    lintScriptText,
    triggerAnchor,
    microNarrative,
  };
})(window);
