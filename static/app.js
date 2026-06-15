const config = {
  papersUrl: document.querySelector('meta[name="papers-url"]').content,
  refreshUrl: document.querySelector('meta[name="refresh-url"]').content,
  mode: document.querySelector('meta[name="deployment-mode"]').content
};

const SECTION_LABELS = {
  arxiv: ["arXiv", "arXiv 最新论文", "ARXIV · LATEST"],
  awards: ["Best Papers", "特别好文专区", "AWARDS · EDITOR'S CHOICE"]
};

const CONFERENCE_TIME_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "1y", label: "近 1 年" },
  { value: "3y", label: "近 3 年" },
  { value: "after2020", label: "2020 年及以后" },
  { value: "custom", label: "自定义范围" }
];

const ARXIV_TIME_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "3d", label: "近 3 天" },
  { value: "7d", label: "近 1 周" },
  { value: "15d", label: "近半个月" },
  { value: "custom", label: "自定义范围" }
];

const CITATION_OPTIONS = [
  { value: "all", label: "不限", min: null, max: null },
  { value: "0-9", label: "0-9", min: 0, max: 9 },
  { value: "10-49", label: "10-49", min: 10, max: 49 },
  { value: "50-199", label: "50-199", min: 50, max: 199 },
  { value: "200-999", label: "200-999", min: 200, max: 999 },
  { value: "1000+", label: "1000+", min: 1000, max: null }
];

const pageState = {
  source: "arxiv",
  timer: null,
  data: null
};

const filterState = {
  categories: new Set(),
  timePreset: "all",
  customFromYear: "",
  customToYear: "",
  citationBucket: "all"
};

const searchState = {
  query: ""
};

const sortState = {
  mode: "date_desc"
};

const viewState = {
  mode: "card",
  filtersExpanded: true
};

const immersiveState = {
  active: false,
  drawerOpen: false,
  scrollY: 0,
  previousView: "card"
};

const grid = document.querySelector("#paperGrid");
const emptyState = document.querySelector("#emptyState");
const sourceTabs = document.querySelector("#sourceTabs");
const searchInput = document.querySelector("#searchInput");
const categoryFacet = document.querySelector("#categoryFacet");
const timeFacet = document.querySelector("#timeFacet");
const citationFacet = document.querySelector("#citationFacet");
const customYearRange = document.querySelector("#customYearRange");
const customFromYear = document.querySelector("#customFromYear");
const customToYear = document.querySelector("#customToYear");
const customFromLabel = document.querySelector("#customFromLabel");
const customToLabel = document.querySelector("#customToLabel");
const activeFilters = document.querySelector("#activeFilters");
const activeFilterTags = document.querySelector("#activeFilterTags");
const emptyFilterLabel = document.querySelector("#emptyFilterLabel");
const clearFiltersButton = document.querySelector("#clearFiltersButton");
const filterToggleButton = document.querySelector("#filterToggleButton");
const facetPanel = document.querySelector("#facetPanel");
const viewSwitcher = document.querySelector(".view-switcher");
const sortSelect = document.querySelector("#sortSelect");
const refreshButton = document.querySelector("#refreshButton");
const sourceNav = document.querySelector(".source-nav");
const searchBox = document.querySelector(".search-box");
const sectionTitleBlock = document.querySelector(".section-title-block");
const resultsTools = document.querySelector(".results-tools");
const immersiveButton = document.querySelector("#immersiveButton");
const immersiveOverlay = document.querySelector("#immersiveOverlay");
const immersiveSearchSlot = document.querySelector("#immersiveSearchSlot");
const immersiveToolsSlot = document.querySelector("#immersiveToolsSlot");
const immersiveSourceSlot = document.querySelector("#immersiveSourceSlot");
const immersiveFacetSlot = document.querySelector("#immersiveFacetSlot");
const immersiveActiveSlot = document.querySelector("#immersiveActiveSlot");
const immersiveHeadingSlot = document.querySelector("#immersiveHeadingSlot");
const immersiveGridSlot = document.querySelector("#immersiveGridSlot");
const immersiveFilterButton = document.querySelector("#immersiveFilterButton");
const exitImmersiveButton = document.querySelector("#exitImmersiveButton");
const closeImmersiveFilters = document.querySelector("#closeImmersiveFilters");
const immersiveBackdrop = document.querySelector("#immersiveBackdrop");

const movableNodes = [
  sourceNav,
  searchBox,
  facetPanel,
  activeFilters,
  sectionTitleBlock,
  resultsTools,
  grid,
  emptyState
];
const nodeAnchors = new Map(
  movableNodes.map(node => {
    const anchor = document.createComment(`restore-${node.className || node.id}`);
    node.parentNode.insertBefore(anchor, node);
    return [node, anchor];
  })
);

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}

function formatDate(value) {
  if (!value) return "未知日期";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    year: "numeric"
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

function paperMatchesSource(paper) {
  if (pageState.source === "arxiv") return paper.source_kind === "arxiv";
  if (pageState.source === "awards") return (paper.awards || []).length > 0;
  return paper.source_kind === "conference" && paper.conference === pageState.source;
}

function paperYear(paper) {
  return Number(paper.publication_year || String(paper.published || "").slice(0, 4) || 0);
}

function paperTimestamp(paper) {
  const timestamp = Number(paper.published_ts || 0);
  if (timestamp) return timestamp * 1000;
  const parsed = Date.parse(paper.published || "");
  return Number.isNaN(parsed) ? 0 : parsed;
}

function paperCitations(paper) {
  return Number(paper.cited_by_count || 0);
}

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function arxivDateBounds() {
  const today = new Date();
  const earliest = new Date(today);
  earliest.setDate(earliest.getDate() - 15);
  return {
    min: formatDateInput(earliest),
    max: formatDateInput(today)
  };
}

function ensureArxivCustomRange() {
  if (pageState.source !== "arxiv") return;
  const bounds = arxivDateBounds();
  if (!filterState.customFromYear) filterState.customFromYear = bounds.min;
  if (!filterState.customToYear) filterState.customToYear = bounds.max;
}

function timeOptionsForSource() {
  return pageState.source === "arxiv"
    ? ARXIV_TIME_OPTIONS
    : CONFERENCE_TIME_OPTIONS;
}

function searchableText(paper) {
  return [
    paper.title,
    paper.summary,
    paper.conference,
    paper.venue,
    ...(paper.authors || []),
    ...(paper.institutions || []),
    ...(paper.embodied_categories || []),
    ...(paper.awards || []).map(item => item.award || "")
  ].join(" ").toLocaleLowerCase();
}

function matchesQuery(paper) {
  const query = searchState.query.toLocaleLowerCase();
  return !query || searchableText(paper).includes(query);
}

function matchesTime(paper) {
  const year = paperYear(paper);
  const now = Date.now();
  if (filterState.timePreset === "3d") {
    return paperTimestamp(paper) >= now - 3 * 24 * 60 * 60 * 1000;
  }
  if (filterState.timePreset === "7d") {
    return paperTimestamp(paper) >= now - 7 * 24 * 60 * 60 * 1000;
  }
  if (filterState.timePreset === "15d") {
    return paperTimestamp(paper) >= now - 15 * 24 * 60 * 60 * 1000;
  }
  if (filterState.timePreset === "1y") {
    return paperTimestamp(paper) >= now - 365 * 24 * 60 * 60 * 1000;
  }
  if (filterState.timePreset === "3y") {
    return paperTimestamp(paper) >= now - 3 * 365 * 24 * 60 * 60 * 1000;
  }
  if (filterState.timePreset === "after2020") return year >= 2020;
  if (filterState.timePreset === "custom") {
    if (pageState.source === "arxiv") {
      const fromTime = filterState.customFromYear
        ? Date.parse(`${filterState.customFromYear}T00:00:00`)
        : null;
      const toTime = filterState.customToYear
        ? Date.parse(`${filterState.customToYear}T23:59:59`)
        : null;
      const timestamp = paperTimestamp(paper);
      return (fromTime === null || timestamp >= fromTime) &&
        (toTime === null || timestamp <= toTime);
    }
    const fromYear = filterState.customFromYear === ""
      ? null
      : Number(filterState.customFromYear);
    const toYear = filterState.customToYear === ""
      ? null
      : Number(filterState.customToYear);
    return (fromYear === null || year >= fromYear) &&
      (toYear === null || year <= toYear);
  }
  return true;
}

function matchesCitations(paper) {
  const bucket = CITATION_OPTIONS.find(
    option => option.value === filterState.citationBucket
  ) || CITATION_OPTIONS[0];
  const citations = paperCitations(paper);
  return (bucket.min === null || citations >= bucket.min) &&
    (bucket.max === null || citations <= bucket.max);
}

function matchesCategories(paper) {
  if (!filterState.categories.size) return true;
  const categories = paper.embodied_categories || [];
  return [...filterState.categories].some(category => categories.includes(category));
}

function baseFacetPapers() {
  if (!pageState.data) return [];
  return pageState.data.papers.filter(paper =>
    paperMatchesSource(paper) &&
    matchesQuery(paper) &&
    matchesTime(paper) &&
    matchesCitations(paper)
  );
}

function filteredPapers() {
  if (!pageState.data) return [];
  return pageState.data.papers.filter(paper =>
    paperMatchesSource(paper) &&
    matchesQuery(paper) &&
    matchesCategories(paper) &&
    matchesTime(paper) &&
    matchesCitations(paper)
  );
}

function relevanceScore(paper) {
  const query = searchState.query.trim().toLocaleLowerCase();
  if (!query) return 0;
  const terms = query.split(/\s+/).filter(Boolean);
  const title = String(paper.title || "").toLocaleLowerCase();
  const summary = String(paper.summary || "").toLocaleLowerCase();
  const people = [
    ...(paper.authors || []),
    ...(paper.institutions || [])
  ].join(" ").toLocaleLowerCase();
  return terms.reduce((score, term) => {
    if (title.includes(term)) score += 8;
    if (people.includes(term)) score += 4;
    if (summary.includes(term)) score += 2;
    return score;
  }, 0);
}

function recommendationScore(paper) {
  const ageInYears = Math.max(
    0,
    (Date.now() - paperTimestamp(paper)) / (365 * 24 * 60 * 60 * 1000)
  );
  const recency = Math.max(0, 6 - ageInYears);
  const citations = Math.log10(paperCitations(paper) + 1) * 2.4;
  const awards = (paper.awards || []).length * 3;
  const categoryAffinity = filterState.categories.size
    ? (paper.embodied_categories || []).filter(
        category => filterState.categories.has(category)
      ).length
    : 0;
  return recency + citations + awards + categoryAffinity;
}

function sortedPapers(papers) {
  const sorted = [...papers];
  sorted.sort((left, right) => {
    if (sortState.mode === "citations_desc") {
      return paperCitations(right) - paperCitations(left) ||
        paperTimestamp(right) - paperTimestamp(left);
    }
    if (sortState.mode === "relevance_desc") {
      return relevanceScore(right) - relevanceScore(left) ||
        paperTimestamp(right) - paperTimestamp(left);
    }
    if (sortState.mode === "recommended_desc") {
      return recommendationScore(right) - recommendationScore(left) ||
        paperTimestamp(right) - paperTimestamp(left);
    }
    return paperTimestamp(right) - paperTimestamp(left);
  });
  return sorted;
}

function renderSourceTabs() {
  const sources = ["arxiv", ...(pageState.data.conferences || []), "awards"];
  sourceTabs.innerHTML = sources.map(source => {
    const [label] = sectionMeta(source);
    const count = pageState.data.section_counts?.[source] || 0;
    return `
      <button class="source-tab ${pageState.source === source ? "active" : ""}"
        data-source="${escapeHtml(source)}" type="button">
        <span>${escapeHtml(label)}</span><strong>${count}</strong>
      </button>
    `;
  }).join("");
}

function renderCategoryFacet() {
  const papers = baseFacetPapers();
  const categories = pageState.data.categories || [];
  const counts = Object.fromEntries(categories.map(category => [category, 0]));
  papers.forEach(paper => {
    (paper.embodied_categories || []).forEach(category => {
      if (category in counts) counts[category] += 1;
    });
  });

  const options = [
    { value: "", label: "全部方向", count: papers.length },
    ...categories.map(category => ({
      value: category,
      label: category,
      count: counts[category] || 0
    }))
  ];

  categoryFacet.innerHTML = options.map(option => {
    const active = option.value
      ? filterState.categories.has(option.value)
      : filterState.categories.size === 0;
    return `
      <button class="facet-option category-option ${active ? "active" : ""}"
        data-category="${escapeHtml(option.value)}" type="button"
        aria-pressed="${active}">
        <span>${escapeHtml(option.label)}</span>
        <strong>${option.count}</strong>
      </button>
    `;
  }).join("");
}

function renderSingleChoiceFacet(container, options, activeValue, dataName) {
  container.innerHTML = options.map(option => {
    const active = option.value === activeValue;
    return `
      <button class="facet-option compact-option ${active ? "active" : ""}"
        data-${dataName}="${escapeHtml(option.value)}" type="button"
        aria-pressed="${active}">
        ${escapeHtml(option.label)}
      </button>
    `;
  }).join("");
}

function timeFilterLabel() {
  if (filterState.timePreset !== "custom") {
    return timeOptionsForSource().find(
      option => option.value === filterState.timePreset
    )?.label || "";
  }
  const fromYear = filterState.customFromYear || "不限";
  const toYear = filterState.customToYear || "不限";
  return `${fromYear}-${toYear}`;
}

function configureCustomRange() {
  const isArxiv = pageState.source === "arxiv";
  customFromLabel.textContent = isArxiv ? "起始日期" : "起始年份";
  customToLabel.textContent = isArxiv ? "结束日期" : "结束年份";
  customFromYear.type = isArxiv ? "date" : "number";
  customToYear.type = isArxiv ? "date" : "number";
  if (isArxiv) {
    const bounds = arxivDateBounds();
    customFromYear.min = bounds.min;
    customFromYear.max = bounds.max;
    customToYear.min = bounds.min;
    customToYear.max = bounds.max;
    customFromYear.placeholder = "";
    customToYear.placeholder = "";
  } else {
    customFromYear.min = "1950";
    customToYear.min = "1950";
    customFromYear.removeAttribute("max");
    customToYear.removeAttribute("max");
    customFromYear.placeholder = "例如 2021";
    customToYear.placeholder = "例如 2026";
  }
}

function activeFilterItems() {
  const items = [...filterState.categories].map(category => ({
    type: "category",
    value: category,
    label: category
  }));
  if (filterState.timePreset !== "all") {
    items.push({
      type: "time",
      value: filterState.timePreset,
      label: timeFilterLabel()
    });
  }
  if (filterState.citationBucket !== "all") {
    const label = CITATION_OPTIONS.find(
      option => option.value === filterState.citationBucket
    )?.label;
    items.push({
      type: "citations",
      value: filterState.citationBucket,
      label: `${label} 引用`
    });
  }
  if (searchState.query) {
    items.push({
      type: "query",
      value: searchState.query,
      label: `搜索：${searchState.query}`
    });
  }
  return items;
}

function renderActiveFilters() {
  const items = activeFilterItems();
  activeFilters.hidden = items.length === 0 &&
    viewState.filtersExpanded &&
    !immersiveState.active;
  emptyFilterLabel.hidden = items.length > 0;
  clearFiltersButton.hidden = items.length === 0;
  activeFilterTags.innerHTML = items.map(item => `
    <button class="active-filter-tag" data-filter-type="${item.type}"
      data-filter-value="${escapeHtml(item.value)}" type="button"
      aria-label="移除筛选：${escapeHtml(item.label)}">
      <span>${escapeHtml(item.label)}</span><strong aria-hidden="true">×</strong>
    </button>
  `).join("");
}

function renderLayoutControls() {
  facetPanel.hidden = immersiveState.active ? false : !viewState.filtersExpanded;
  filterToggleButton.textContent = viewState.filtersExpanded
    ? "收起筛选"
    : "展开筛选";
  filterToggleButton.setAttribute(
    "aria-expanded",
    String(viewState.filtersExpanded)
  );
  grid.classList.toggle("view-list", viewState.mode === "list");
  grid.classList.toggle("view-card", viewState.mode === "card");
  viewSwitcher.querySelectorAll("[data-view]").forEach(button => {
    const active = button.dataset.view === viewState.mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function renderFacets() {
  renderCategoryFacet();
  configureCustomRange();
  renderSingleChoiceFacet(
    timeFacet,
    timeOptionsForSource(),
    filterState.timePreset,
    "time"
  );
  renderSingleChoiceFacet(
    citationFacet,
    CITATION_OPTIONS,
    filterState.citationBucket,
    "citations"
  );
  customYearRange.hidden = filterState.timePreset !== "custom";
  customFromYear.value = filterState.customFromYear;
  customToYear.value = filterState.customToYear;
  renderActiveFilters();
}

function renderPapers(papers) {
  grid.hidden = papers.length === 0;
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
    const sourceLabel = paper.venue ||
      (paper.source_kind === "arxiv" ? "arXiv" : paper.conference || "");
    const titleLength = String(paper.title || "").length;
    const authorLength = (paper.authors || []).join(", ").length;
    const summaryLines = Math.min(
      8,
      5 + (titleLength < 75 ? 2 : titleLength < 120 ? 1 : 0) +
        (authorLength < 90 ? 1 : 0)
    );
    return `
      <article class="paper-card"
        style="--delay:${Math.min(index, 12) * 35}ms;--summary-lines:${summaryLines}">
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
        <p class="metadata-line">
          <span>${escapeHtml(sourceLabel)}</span>
          <span>引用 <strong class="citation-count">${paperCitations(paper).toLocaleString("zh-CN")}</strong> 次</span>
          <span class="institution-meta">团队单位：${escapeHtml(institutions)}</span>
        </p>
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

function renderCurrentView() {
  if (!pageState.data) return;
  const papers = sortedPapers(filteredPapers());
  const [, title, eyebrow] = sectionMeta(pageState.source);
  renderSourceTabs();
  renderFacets();
  renderPapers(papers);
  renderLayoutControls();
  document.querySelector("#sectionTitle").textContent = title;
  document.querySelector("#sectionEyebrow").textContent = eyebrow;
  document.querySelector("#paperCount").textContent = papers.length;
  document.querySelector("#sectionCount").textContent =
    (pageState.data.conferences || []).length + 2;
  document.querySelector("#resultHint").textContent = pageState.data.last_error
    ? `部分数据更新异常：${pageState.data.last_error}`
    : `显示 ${papers.length} 篇符合条件的论文`;
}

async function loadPapers() {
  try {
    const response = await fetch(config.papersUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    pageState.data = await response.json();
    renderCurrentView();
    document.querySelector("#updatedAt").textContent = pageState.data.updated_at
      ? new Intl.DateTimeFormat("zh-CN", {
          month: "numeric",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit"
        }).format(new Date(pageState.data.updated_at))
      : "等待首次同步";
    if (config.mode === "static") {
      refreshButton.textContent = "GitHub 自动更新";
      refreshButton.disabled = true;
      refreshButton.classList.remove("is-refreshing");
    } else {
      refreshButton.disabled = pageState.data.refreshing;
      refreshButton.textContent = pageState.data.refreshing ? "正在刷新…" : "立即刷新";
      refreshButton.classList.toggle("is-refreshing", pageState.data.refreshing);
      if (pageState.data.refreshing) schedulePoll();
    }
  } catch (error) {
    document.querySelector("#resultHint").textContent = "无法连接到服务";
  }
}

function schedulePoll() {
  clearTimeout(pageState.timer);
  pageState.timer = setTimeout(loadPapers, 2500);
}

function resetFilters() {
  searchState.query = "";
  filterState.categories.clear();
  filterState.timePreset = "all";
  filterState.customFromYear = "";
  filterState.customToYear = "";
  filterState.citationBucket = "all";
  searchInput.value = "";
}

function restoreNode(node) {
  const anchor = nodeAnchors.get(node);
  anchor.parentNode.insertBefore(node, anchor.nextSibling);
}

function renderImmersiveState() {
  immersiveOverlay.hidden = !immersiveState.active;
  document.body.classList.toggle("immersive-open", immersiveState.active);
  immersiveOverlay.classList.toggle("drawer-open", immersiveState.drawerOpen);
  immersiveFilterButton.setAttribute(
    "aria-expanded",
    String(immersiveState.drawerOpen)
  );
}

function enterImmersiveMode() {
  if (immersiveState.active) return;
  immersiveState.scrollY = window.scrollY;
  immersiveState.previousView = viewState.mode;
  immersiveState.active = true;
  immersiveState.drawerOpen = false;
  viewState.mode = "list";

  immersiveSearchSlot.append(searchBox);
  immersiveToolsSlot.append(resultsTools);
  immersiveSourceSlot.append(sourceNav);
  immersiveFacetSlot.append(facetPanel);
  immersiveActiveSlot.append(activeFilters);
  immersiveHeadingSlot.append(sectionTitleBlock);
  immersiveGridSlot.append(grid, emptyState);

  renderCurrentView();
  renderImmersiveState();
  searchInput.focus();
}

function exitImmersiveMode() {
  if (!immersiveState.active) return;
  immersiveState.active = false;
  immersiveState.drawerOpen = false;
  viewState.mode = immersiveState.previousView;
  movableNodes.forEach(restoreNode);
  renderCurrentView();
  renderImmersiveState();
  window.scrollTo(0, immersiveState.scrollY);
}

function setImmersiveDrawer(open) {
  immersiveState.drawerOpen = open;
  renderImmersiveState();
}

sourceTabs.addEventListener("click", event => {
  const button = event.target.closest("[data-source]");
  if (!button) return;
  pageState.source = button.dataset.source;
  filterState.timePreset = "all";
  filterState.customFromYear = "";
  filterState.customToYear = "";
  renderCurrentView();
});

categoryFacet.addEventListener("click", event => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  const category = button.dataset.category;
  if (!category) {
    filterState.categories.clear();
  } else if (filterState.categories.has(category)) {
    filterState.categories.delete(category);
  } else {
    filterState.categories.add(category);
  }
  renderCurrentView();
});

timeFacet.addEventListener("click", event => {
  const button = event.target.closest("[data-time]");
  if (!button) return;
  filterState.timePreset = button.dataset.time;
  if (filterState.timePreset === "custom") ensureArxivCustomRange();
  renderCurrentView();
  if (filterState.timePreset === "custom") customFromYear.focus();
});

citationFacet.addEventListener("click", event => {
  const button = event.target.closest("[data-citations]");
  if (!button) return;
  filterState.citationBucket = button.dataset.citations;
  renderCurrentView();
});

[customFromYear, customToYear].forEach(control => {
  control.addEventListener("input", () => {
    filterState.customFromYear = customFromYear.value;
    filterState.customToYear = customToYear.value;
    renderCurrentView();
  });
});

activeFilterTags.addEventListener("click", event => {
  const button = event.target.closest("[data-filter-type]");
  if (!button) return;
  const type = button.dataset.filterType;
  if (type === "category") {
    filterState.categories.delete(button.dataset.filterValue);
  } else if (type === "time") {
    filterState.timePreset = "all";
    filterState.customFromYear = "";
    filterState.customToYear = "";
  } else if (type === "citations") {
    filterState.citationBucket = "all";
  } else if (type === "query") {
    searchState.query = "";
    searchInput.value = "";
  }
  renderCurrentView();
});

searchInput.addEventListener("input", () => {
  clearTimeout(pageState.timer);
  pageState.timer = setTimeout(() => {
    searchState.query = searchInput.value.trim();
    renderCurrentView();
  }, 150);
});

sortSelect.addEventListener("change", () => {
  sortState.mode = sortSelect.value;
  renderCurrentView();
});

clearFiltersButton.addEventListener("click", () => {
  resetFilters();
  renderCurrentView();
});

filterToggleButton.addEventListener("click", () => {
  viewState.filtersExpanded = !viewState.filtersExpanded;
  renderCurrentView();
});

viewSwitcher.addEventListener("click", event => {
  const button = event.target.closest("[data-view]");
  if (!button) return;
  viewState.mode = button.dataset.view;
  renderLayoutControls();
});

immersiveButton.addEventListener("click", enterImmersiveMode);
exitImmersiveButton.addEventListener("click", exitImmersiveMode);
immersiveFilterButton.addEventListener("click", () => {
  setImmersiveDrawer(!immersiveState.drawerOpen);
});
closeImmersiveFilters.addEventListener("click", () => {
  setImmersiveDrawer(false);
});
immersiveBackdrop.addEventListener("click", () => {
  setImmersiveDrawer(false);
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && immersiveState.active) {
    if (immersiveState.drawerOpen) {
      setImmersiveDrawer(false);
    } else {
      exitImmersiveMode();
    }
  }
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
