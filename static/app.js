const config = {
  papersUrl: document.querySelector('meta[name="papers-url"]').content,
  refreshUrl: document.querySelector('meta[name="refresh-url"]').content,
  mode: document.querySelector('meta[name="deployment-mode"]').content
};
const state = { category: "", query: "", timer: null, data: null };

const grid = document.querySelector("#paperGrid");
const emptyState = document.querySelector("#emptyState");
const filters = document.querySelector("#categoryFilters");
const searchInput = document.querySelector("#searchInput");
const refreshButton = document.querySelector("#refreshButton");

function escapeHtml(value = "") {
  return value.replace(/[&<>"']/g, char => ({
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

function renderFilters(categories) {
  const items = ["", ...categories];
  filters.innerHTML = items.map(category => `
    <button class="filter ${state.category === category ? "active" : ""}"
      data-category="${escapeHtml(category)}" type="button">
      ${category || "全部方向"}
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
      : "arXiv 未提供，OpenAlex 暂未匹配";
    return `
      <article class="paper-card" style="--delay:${Math.min(index, 12) * 35}ms">
        <div class="card-top">
          <div class="tags">${paper.embodied_categories.map(tag => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
          <time>${formatDate(paper.published)}</time>
        </div>
        <h3>${escapeHtml(paper.title)}</h3>
        <p class="authors">${escapeHtml(paper.authors.join(", "))}</p>
        <p class="summary">${escapeHtml(paper.summary)}</p>
        <dl class="metadata">
          <div><dt>团队单位</dt><dd>${escapeHtml(institutions)}</dd></div>
          <div><dt>arXiv 分类</dt><dd>${escapeHtml(paper.arxiv_categories.join(" · "))}</dd></div>
        </dl>
        <div class="card-actions">
          ${externalLink(paper.arxiv_url, "论文详情")}
          ${externalLink(paper.pdf_url, "PDF", "text-link")}
          ${externalLink(projectUrl, "项目 / 代码", "text-link")}
        </div>
      </article>
    `;
  }).join("");
  emptyState.hidden = papers.length > 0;
}

function filteredPapers() {
  if (!state.data) return [];
  const query = state.query.toLocaleLowerCase();
  return state.data.papers.filter(paper => {
    const categoryMatches = !state.category ||
      paper.embodied_categories.includes(state.category);
    const searchable = [
      paper.title,
      paper.summary,
      ...(paper.authors || []),
      ...(paper.institutions || [])
    ].join(" ").toLocaleLowerCase();
    return categoryMatches && (!query || searchable.includes(query));
  });
}

function renderCurrentView() {
  const papers = filteredPapers();
  renderFilters(state.data.categories);
  renderPapers(papers);
  document.querySelector("#paperCount").textContent = papers.length;
  document.querySelector("#categoryCount").textContent = state.data.categories.length;
  document.querySelector("#resultHint").textContent = state.data.last_error
    ? `同步异常：${state.data.last_error}`
    : `显示 ${papers.length} 篇符合条件的论文`;
}

async function loadPapers() {
  try {
    const response = await fetch(config.papersUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.data = data;
    renderCurrentView();
    document.querySelector("#updatedAt").textContent = data.updated_at
      ? new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(data.updated_at))
      : "等待首次同步";
    if (config.mode === "static") {
      refreshButton.textContent = "GitHub 自动更新";
      refreshButton.disabled = true;
      document.querySelector("#emptyHint").textContent =
        "GitHub Actions 会按计划自动同步；也可以在 Actions 页面手动运行更新。";
    } else {
      refreshButton.disabled = data.refreshing;
      refreshButton.textContent = data.refreshing ? "正在刷新…" : "立即刷新";
      if (data.refreshing) schedulePoll();
    }
  } catch (error) {
    document.querySelector("#resultHint").textContent = "无法连接到服务";
  }
}

function schedulePoll() {
  clearTimeout(state.timer);
  state.timer = setTimeout(loadPapers, 2500);
}

filters.addEventListener("click", event => {
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

refreshButton.addEventListener("click", async () => {
  if (config.mode === "static") return;
  refreshButton.disabled = true;
  refreshButton.textContent = "正在刷新…";
  await fetch(config.refreshUrl, { method: "POST" });
  schedulePoll();
});

loadPapers();
