const config = {
  papersUrl: document.querySelector('meta[name="papers-url"]').content,
  refreshUrl: document.querySelector('meta[name="refresh-url"]').content,
  mode: document.querySelector('meta[name="deployment-mode"]').content
};

const SECTION_LABELS = {
  arxiv: ["arXiv", "arXiv 最新论文", "ARXIV · LATEST"],
  awards: ["Best Papers", "特别好文专区", "AWARDS · EDITOR'S CHOICE"]
};
const state = {
  source: "arxiv",
  category: "",
  query: "",
  sort: "date_desc",
  fromYear: "",
  toYear: "",
  minCitations: "",
  maxCitations: "",
  timer: null,
  data: null
};

const grid = document.querySelector("#paperGrid");
const emptyState = document.querySelector("#emptyState");
const sourceTabs = document.querySelector("#sourceTabs");
const searchInput = document.querySelector("#searchInput");
const categoryFilters = document.querySelector("#categoryFilters");
const sortSelect = document.querySelector("#sortSelect");
const fromYearInput = document.querySelector("#fromYearInput");
const toYearInput = document.querySelector("#toYearInput");
const minCitationsInput = document.querySelector("#minCitationsInput");
const maxCitationsInput = document.querySelector("#maxCitationsInput");
const clearFiltersButton = document.querySelector("#clearFiltersButton");
const refreshButton = document.querySelector("#refreshButton");

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);
}

function formatDate(value) {
  if (!value) return "未知日期";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short", day: "numeric", year: "numeric"
  }).format(new Date(value));
}

function externalLink(url, label, className = "link-button") {
  if (!url) return "";
  return `<a class="${className}" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${label}<span>↗</span></a>`;
}

function sectionMeta(source) {
  if (SECTION_LABELS[source]) return SECTION_LABELS[source];
  return [source, `${source} 会议论文`, `CONFERENCE · ${source}`];
}

function renderSourceTabs() {
  const sources = ["arxiv", ...(state.data.conferences || []), "awards"];
  sourceTabs.innerHTML = sources.map(source => {
    const [label] = sectionMeta(source);
    const count = state.data.section_counts?.[source] || 0;
    return `
      <button class="source-tab ${state.source === source ? "active" : ""}"
        data-source="${escapeHtml(source)}" type="button">
        <span>${escapeHtml(label)}</span><strong>${count}</strong>
      </button>
    `;
  }).join("");
}

function renderCategoryFilters() {
  const categories = ["", ...(state.data.categories || [])];
  categoryFilters.innerHTML = categories.map(category => `
    <button class="category-filter ${state.category === category ? "active" : ""}"
      data-category="${escapeHtml(category)}" type="button">
      ${escapeHtml(category || "全部方向")}
    </button>
  `).join("");
}

function renderPapers(papers) {
  grid.innerHTML = papers.map((paper, index) => {
    const projectUrl = (paper.external_urls || []).find(url =>
      /github\.com|gitlab\.com|project|\.io|\.ai/i.test(url)
    ) || (paper.external_urls || [])[0];
    const institutions = paper.institutions?.length
      ? paper.institutions.join(" · ")
      : "暂未匹配";
    const awards = (paper.awards || []).map(item =>
      `<a class="award-badge" href="${escapeHtml(item.source_url || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.award || "Best Paper")}</a>`
    ).join("");
    const sourceTag = paper.source_kind === "conference"
      ? `<span class="conference-tag">${escapeHtml(paper.conference)}</span>`
      : '<span class="arxiv-tag">arXiv</span>';
    const paperUrl = paper.paper_url || paper.arxiv_url || paper.doi_url;
    return `
      <article class="paper-card" style="--delay:${Math.min(index, 12) * 35}ms">
        <div class="card-top">
          <div class="tags">
            ${sourceTag}${awards}
            ${(paper.embodied_categories || []).map(tag => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
          <time>${formatDate(paper.published)}</time>
        </div>
        <h3>${escapeHtml(paper.title)}</h3>
        <p class="authors">${escapeHtml((paper.authors || []).join(", "))}</p>
        <p class="summary">${escapeHtml(paper.summary || "暂无摘要。")}</p>
        <dl class="metadata">
          <div><dt>来源</dt><dd>${escapeHtml(paper.venue || (paper.source_kind === "arxiv" ? "arXiv" : paper.conference || ""))}</dd></div>
          <div><dt>引用量</dt><dd><strong class="citation-count">${Number(paper.cited_by_count || 0).toLocaleString("zh-CN")}</strong> 次</dd></div>
          <div><dt>团队单位</dt><dd>${escapeHtml(institutions)}</dd></div>
        </dl>
        <div class="card-actions">
          ${externalLink(paperUrl, "论文详情")}
          ${externalLink(paper.pdf_url, "PDF", "text-link")}
          ${externalLink(projectUrl, "项目 / 代码", "text-link")}
        </div>
      </article>
    `;
  }).join("");
  emptyState.hidden = papers.length > 0;
}

function numericValue(value) {
  return value === "" ? null : Number(value);
}

function filteredPapers() {
  if (!state.data) return [];
  const query = state.query.toLocaleLowerCase();
  const fromYear = numericValue(state.fromYear);
  const toYear = numericValue(state.toYear);
  const minCitations = numericValue(state.minCitations);
  const maxCitations = numericValue(state.maxCitations);
  const papers = state.data.papers.filter(paper => {
    const sourceMatches = state.source === "arxiv"
      ? paper.source_kind === "arxiv"
      : state.source === "awards"
        ? (paper.awards || []).length > 0
        : paper.source_kind === "conference" && paper.conference === state.source;
    const categoryMatches = !state.category ||
      (paper.embodied_categories || []).includes(state.category);
    const year = Number(paper.publication_year || 0);
    const citations = Number(paper.cited_by_count || 0);
    const searchable = [
      paper.title, paper.summary, paper.conference,
      ...(paper.authors || []), ...(paper.institutions || []),
      ...(paper.awards || []).map(item => item.award || "")
    ].join(" ").toLocaleLowerCase();
    return sourceMatches && categoryMatches &&
      (fromYear === null || year >= fromYear) &&
      (toYear === null || year <= toYear) &&
      (minCitations === null || citations >= minCitations) &&
      (maxCitations === null || citations <= maxCitations) &&
      (!query || searchable.includes(query));
  });
  const direction = state.sort.endsWith("_desc") ? -1 : 1;
  const field = state.sort.startsWith("citations") ? "cited_by_count" : "published_ts";
  return papers.sort((left, right) =>
    direction * (Number(left[field] || 0) - Number(right[field] || 0))
  );
}

function renderCurrentView() {
  const papers = filteredPapers();
  const [, title, eyebrow] = sectionMeta(state.source);
  renderSourceTabs();
  renderCategoryFilters();
  renderPapers(papers);
  document.querySelector("#sectionTitle").textContent = title;
  document.querySelector("#sectionEyebrow").textContent = eyebrow;
  document.querySelector("#paperCount").textContent = papers.length;
  document.querySelector("#sectionCount").textContent =
    (state.data.conferences || []).length + 2;
  document.querySelector("#resultHint").textContent = state.data.last_error
    ? `部分数据更新异常：${state.data.last_error}`
    : `显示 ${papers.length} 篇符合条件的论文`;
}

async function loadPapers() {
  try {
    const response = await fetch(config.papersUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    renderCurrentView();
    document.querySelector("#updatedAt").textContent = state.data.updated_at
      ? new Intl.DateTimeFormat("zh-CN", {
          month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"
        }).format(new Date(state.data.updated_at))
      : "等待首次同步";
    if (config.mode === "static") {
      refreshButton.textContent = "GitHub 自动更新";
      refreshButton.disabled = true;
      refreshButton.classList.remove("is-refreshing");
    } else {
      refreshButton.disabled = state.data.refreshing;
      refreshButton.textContent = state.data.refreshing ? "正在刷新…" : "立即刷新";
      refreshButton.classList.toggle("is-refreshing", state.data.refreshing);
      if (state.data.refreshing) schedulePoll();
    }
  } catch (error) {
    document.querySelector("#resultHint").textContent = "无法连接到服务";
  }
}

function schedulePoll() {
  clearTimeout(state.timer);
  state.timer = setTimeout(loadPapers, 2500);
}

function syncFilters() {
  state.sort = sortSelect.value;
  state.fromYear = fromYearInput.value;
  state.toYear = toYearInput.value;
  state.minCitations = minCitationsInput.value;
  state.maxCitations = maxCitationsInput.value;
  renderCurrentView();
}

sourceTabs.addEventListener("click", event => {
  const button = event.target.closest("[data-source]");
  if (!button) return;
  state.source = button.dataset.source;
  renderCurrentView();
});

[sortSelect, fromYearInput, toYearInput, minCitationsInput, maxCitationsInput]
  .forEach(control => control.addEventListener("change", syncFilters));

categoryFilters.addEventListener("click", event => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  renderCurrentView();
});

searchInput.addEventListener("input", () => {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => {
    state.query = searchInput.value.trim();
    renderCurrentView();
  }, 250);
});

clearFiltersButton.addEventListener("click", () => {
  state.category = "";
  state.query = "";
  state.sort = "date_desc";
  state.fromYear = "";
  state.toYear = "";
  state.minCitations = "";
  state.maxCitations = "";
  searchInput.value = "";
  sortSelect.value = "date_desc";
  [fromYearInput, toYearInput, minCitationsInput, maxCitationsInput]
    .forEach(control => { control.value = ""; });
  renderCurrentView();
});

refreshButton.addEventListener("click", async () => {
  if (config.mode === "static") return;
  refreshButton.disabled = true;
  refreshButton.textContent = "正在刷新…";
  refreshButton.classList.add("is-refreshing");
  await fetch(config.refreshUrl, { method: "POST" });
  schedulePoll();
});

loadPapers();
