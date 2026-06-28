import fs from "fs"
import path from "path"

const root = path.resolve(".")

function replaceBetween(content, startMarker, endMarker, replacement) {
  const start = content.indexOf(startMarker)
  const end = content.indexOf(endMarker, start)
  if (start === -1 || end === -1) {
    throw new Error(`Markers not found: ${startMarker}`)
  }
  return content.slice(0, start) + replacement + content.slice(end + endMarker.length)
}

// --- prompt-generator ---
const promptPath = path.join(root, "site/prompt-generator.html")
let prompt = fs.readFileSync(promptPath, "utf8")

const promptDataBlock = `let FOODS = [];
let KNOWLEDGE = [];

function mapFood(f) {
  return {
    id: f.id,
    name: f.name_zh,
    en: f.name_en,
    cat: f.category,
    sub: f.subcategory,
    gi: f.gi,
    giLevel: f.gi_level,
    gl: f.gl_per_serving,
    glLevel: f.gl_level,
    cal: f.calories_per_100g,
    carbs: f.carbs_per_100g,
    protein: f.protein_per_100g,
    fat: f.fat_per_100g,
    fiber: f.fiber_per_100g,
    impact: f.blood_sugar_impact,
    serving: f.serving_desc,
    timing: f.best_timing,
    suitable: f.suitable_for,
    caution: f.caution_for,
    tips: f.tips || [],
    combos: f.recommended_combos || [],
    src: f.data_sources || "",
  };
}

function mapKnowledge(t, idx) {
  return {
    id: \`k\${String(idx + 1).padStart(2, "0")}\`,
    title: t.title_zh,
    cat: t.category,
    summary: t.summary,
    points: t.key_points || [],
    visType: t.visual_type || "信息图",
  };
}

async function loadPromptData() {
  const [foodsRes, topicsRes] = await Promise.all([
    fetch("../data/foods/gi-database.json"),
    fetch("../data/knowledge/topics.json"),
  ]);
  if (!foodsRes.ok || !topicsRes.ok) {
    throw new Error("数据加载失败");
  }
  const foodsData = await foodsRes.json();
  const topicsData = await topicsRes.json();
  FOODS = (foodsData.foods || []).map(mapFood);
  KNOWLEDGE = (topicsData.topics || []).map(mapKnowledge);
}

`

prompt = replaceBetween(prompt, "const FOODS=[", "];", promptDataBlock)
prompt = replaceBetween(prompt, "\nconst KNOWLEDGE=[", "];", "\n")
prompt = prompt.replace("// INIT\nrenderStep2();", `// INIT
loadPromptData()
  .then(() => renderStep2())
  .catch(() => {
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="background:#fef5f0;color:#c44d3a;padding:12px;text-align:center">数据加载失败，请通过本地服务器访问</div>'
    );
  });`)

fs.writeFileSync(promptPath, prompt)

// --- script-generator ---
const scriptPath = path.join(root, "site/script-generator.html")
let script = fs.readFileSync(scriptPath, "utf8")

const topicsBlock = `let TOPICS = [];

async function loadTopicsLibrary() {
  const res = await fetch("../data/knowledge/script-topics.json");
  if (!res.ok) throw new Error("topics load failed");
  const data = await res.json();
  TOPICS = data.topics || [];
}

`

script = replaceBetween(script, "const TOPICS=[", "];", topicsBlock)

script = script.replace(
  /const EMBEDDED_DISCOVERED=`[\s\S]*?`;\s*/,
  "",
)

script = script.replace(
  `  }else{
    try{ DISCOVERED_TOPICS=JSON.parse(EMBEDDED_DISCOVERED); }catch(e){ DISCOVERED_TOPICS=[]; }
  }`,
  `  }else{
    try{
      const res=await fetch("../data/discovered-topics.json");
      if(res.ok){
        const data=await res.json();
        DISCOVERED_TOPICS=data.topics||[];
      }
    }catch(e){ DISCOVERED_TOPICS=[]; }
  }`,
)

script = script.replace(
  "function loadDiscoveredTopics(){",
  "async function loadDiscoveredTopics(){",
)

script = script.replace(
  `(function init(){
  const cats=[...new Set(TOPICS.map(t=>t.catName))];
  const sel=document.getElementById("filter-cat");
  cats.forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o)});
  renderTopics();
  loadDiscoveredTopics();
})();`,
  `(async function init(){
  try{
    await loadTopicsLibrary();
    const cats=[...new Set(TOPICS.map(t=>t.catName))];
    const sel=document.getElementById("filter-cat");
    cats.forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o)});
    renderTopics();
    await loadDiscoveredTopics();
  }catch(e){
    document.body.insertAdjacentHTML("afterbegin", '<div style="background:#fef5f0;color:#c44d3a;padding:12px;text-align:center">选题数据加载失败，请通过本地服务器访问</div>');
  }
})();`,
)

fs.writeFileSync(scriptPath, script)
console.log("Refactored site HTML tools")
