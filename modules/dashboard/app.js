const STORAGE_KEY = "battery-dev-log-status-v1";

const entries = [
  {
    id: "2026-05-21-factor-table",
    date: "2026-05-21",
    priority: "P0",
    module: "Research Planning",
    title: "建立智能电池系统因素总表",
    detail:
      "围绕 RUL 预测、策略优化、实验控制、GUI 自动化、安全约束和实验追溯建立研发因素清单。",
    keywords: ["因素", "总表", "系统", "科研方向", "规划"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-22-branch-plan",
    date: "2026-05-22",
    priority: "P0",
    module: "Git",
    title: "按模块拆分开发分支",
    detail:
      "建立 data-pipeline、feature-engineering、rul-prediction、strategy-optimizer、dashboard 等分支，支持并行开发。",
    keywords: ["分支", "branch", "git", "dashboard", "feature-engineering"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-22-model-by-chemistry",
    date: "2026-05-22",
    priority: "P1",
    module: "Model Strategy",
    title: "采用分类型专用模型与通用基础特征体系",
    detail:
      "数据格式和特征体系保持统一，模型按电池体系或数据来源分科训练，并保留迁移学习路径。",
    keywords: ["电池类型", "分类型", "lfp", "nmc", "nca", "迁移学习"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-24-nasa-preprocess",
    date: "2026-05-24",
    priority: "P0",
    module: "Data Pipeline",
    title: "预处理 NASA B0005/B0006/B0007/B0018",
    detail:
      "将 .mat 数据拆分为 raw 与 processed，输出 cycle_summary、充放电时序、阻抗谱和 manifest。",
    keywords: ["nasa", "预处理", "mat", "cycle_summary", "raw", "processed"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-26-data-quality",
    date: "2026-05-26",
    priority: "P0",
    module: "Data Pipeline",
    title: "补充数据质量报告与 Parquet 输出",
    detail:
      "检查缺失值、时间递增、物理范围、容量跳变、阻抗异常，并将大时序 CSV 同步转换为 Parquet。",
    keywords: ["数据质量", "quality", "parquet", "缺失值", "异常"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-27-soh-rul-features",
    date: "2026-05-27",
    priority: "P0",
    module: "Feature Engineering",
    title: "生成 SOH/RUL 标签和循环级特征表",
    detail:
      "基于放电容量定义 SOH，按 EOL 阈值生成 RUL，正确标记右删失样本，并生成循环级特征表。",
    keywords: ["soh", "rul", "标签", "特征", "feature", "右删失"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-27-cross-validation",
    date: "2026-05-27",
    priority: "P0",
    module: "RUL Prediction",
    title: "建立 Leave-One-Battery-Out 验证",
    detail:
      "避免随机打乱导致数据泄漏，按 B0005/B0006/B0007/B0018 做跨电池泛化验证。",
    keywords: ["验证", "leave-one", "cross", "泛化", "数据泄漏"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-27-baseline-models",
    date: "2026-05-27",
    priority: "P1",
    module: "RUL Prediction",
    title: "先建立 Ridge、Random Forest、XGBoost 等基线模型",
    detail:
      "先用结构化循环特征训练可解释基线，再考虑 LSTM、GRU 或更复杂的序列模型。",
    keywords: ["baseline", "ridge", "random forest", "xgboost", "模型"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-29-rul-ablation-uncertainty",
    date: "2026-05-29",
    priority: "P0",
    module: "RUL Prediction",
    title: "完成 RUL 特征消融与不确定性估计",
    detail:
      "在 Leave-One-Battery-Out 基线中加入残差分位数预测区间，并输出特征组消融结果，用于判断容量、电压、温度、阻抗等特征对 RUL 预测的影响。",
    keywords: ["rul", "不确定性", "预测区间", "特征消融", "ablation", "uncertainty"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-27-strategy-data",
    date: "2026-05-27",
    priority: "P1",
    module: "Strategy Optimizer",
    title: "策略优化需引入真实动作反馈数据",
    detail:
      "NASA 数据适合寿命预测，但不足以训练策略优化；后续需要记录 action、状态、反馈和 reward。",
    keywords: ["策略", "reward", "action", "强化学习", "贝叶斯优化"],
    defaultStatus: "todo",
  },
  {
    id: "2026-05-28-dev-log-mvp",
    date: "2026-05-28",
    priority: "P1",
    module: "Dashboard",
    title: "建立开发日志 MVP 界面",
    detail:
      "按日期整理建议，支持优先级、已执行/未执行状态、本地保存和操作关键词自动匹配。",
    keywords: ["开发日志", "mvp", "dashboard", "界面", "状态"],
    defaultStatus: "done",
  },
  {
    id: "2026-05-28-gui-automation-plan",
    date: "2026-05-28",
    priority: "P2",
    module: "GUI Automation",
    title: "后续设计无 API 设备的 GUI 自动化守护流程",
    detail:
      "为无 API 实验设备准备截图识别、OCR、鼠标键盘动作、点击前后状态校验和失败恢复机制。",
    keywords: ["gui", "自动化", "鼠标", "ocr", "设备"],
    defaultStatus: "todo",
  },
];

const statusFilter = document.querySelector("#status-filter");
const priorityFilter = document.querySelector("#priority-filter");
const searchInput = document.querySelector("#search-input");
const timeline = document.querySelector("#timeline");
const operationForm = document.querySelector("#operation-form");
const operationInput = document.querySelector("#operation-input");
const matchFeedback = document.querySelector("#match-feedback");

function loadStatusMap() {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  const statusMap = {};
  entries.forEach((entry) => {
    statusMap[entry.id] = saved[entry.id] || entry.defaultStatus;
  });
  return statusMap;
}

let statusMap = loadStatusMap();

function saveStatusMap() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(statusMap));
}

function priorityRank(priority) {
  return { P0: 0, P1: 1, P2: 2 }[priority] ?? 3;
}

function visibleEntries() {
  const statusValue = statusFilter.value;
  const priorityValue = priorityFilter.value;
  const query = searchInput.value.trim().toLowerCase();

  return entries
    .filter((entry) => {
      const currentStatus = statusMap[entry.id];
      if (statusValue !== "all" && currentStatus !== statusValue) return false;
      if (priorityValue !== "all" && entry.priority !== priorityValue) return false;
      if (!query) return true;
      const haystack = [
        entry.date,
        entry.priority,
        entry.module,
        entry.title,
        entry.detail,
        ...entry.keywords,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .sort((a, b) => {
      if (a.date !== b.date) return b.date.localeCompare(a.date);
      return priorityRank(a.priority) - priorityRank(b.priority);
    });
}

function updateStats() {
  const doneCount = entries.filter((entry) => statusMap[entry.id] === "done").length;
  const todoCount = entries.length - doneCount;
  const highCount = entries.filter((entry) => entry.priority === "P0").length;
  document.querySelector("#total-count").textContent = entries.length;
  document.querySelector("#done-count").textContent = doneCount;
  document.querySelector("#todo-count").textContent = todoCount;
  document.querySelector("#high-count").textContent = highCount;
}

function groupByDate(items) {
  return items.reduce((groups, item) => {
    groups[item.date] ||= [];
    groups[item.date].push(item);
    return groups;
  }, {});
}

function render() {
  updateStats();
  const items = visibleEntries();
  timeline.innerHTML = "";

  if (!items.length) {
    timeline.innerHTML = '<div class="date-group empty">没有匹配的开发建议。</div>';
    return;
  }

  const grouped = groupByDate(items);
  Object.entries(grouped).forEach(([date, dateEntries]) => {
    const group = document.createElement("article");
    group.className = "date-group";

    const completed = dateEntries.filter((entry) => statusMap[entry.id] === "done").length;
    group.innerHTML = `
      <header class="date-header">
        <h2>${date}</h2>
        <span>${completed}/${dateEntries.length} 已执行</span>
      </header>
      <div class="log-list"></div>
    `;

    const list = group.querySelector(".log-list");
    dateEntries.forEach((entry) => {
      const currentStatus = statusMap[entry.id];
      const item = document.createElement("article");
      item.className = `log-item ${currentStatus}`;
      item.innerHTML = `
        <div class="item-main">
          <div class="item-meta">
            <span class="pill priority-${entry.priority}">${entry.priority}</span>
            <span class="pill module-pill">${entry.module}</span>
            <span class="pill status-pill">${currentStatus === "done" ? "已执行" : "未执行"}</span>
          </div>
          <h3>${entry.title}</h3>
          <p>${entry.detail}</p>
        </div>
        <button class="status-button ${currentStatus === "done" ? "todo-button" : ""}" data-id="${entry.id}">
          ${currentStatus === "done" ? "改为未执行" : "标记已执行"}
        </button>
      `;
      list.appendChild(item);
    });

    timeline.appendChild(group);
  });
}

function toggleStatus(id) {
  statusMap[id] = statusMap[id] === "done" ? "todo" : "done";
  saveStatusMap();
  render();
}

function autoCompleteFromOperation(text) {
  const normalized = text.toLowerCase();
  const matched = [];
  entries.forEach((entry) => {
    const hits = entry.keywords.some((keyword) => normalized.includes(keyword.toLowerCase()));
    if (hits && statusMap[entry.id] !== "done") {
      statusMap[entry.id] = "done";
      matched.push(entry.title);
    }
  });
  if (matched.length) {
    saveStatusMap();
    matchFeedback.textContent = `已自动切换 ${matched.length} 条：${matched.join("；")}`;
  } else {
    matchFeedback.textContent = "未匹配到未执行建议，记录已保留在本次页面会话中。";
  }
  render();
}

timeline.addEventListener("click", (event) => {
  const button = event.target.closest("[data-id]");
  if (!button) return;
  toggleStatus(button.dataset.id);
});

[statusFilter, priorityFilter, searchInput].forEach((control) => {
  control.addEventListener("input", render);
});

operationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = operationInput.value.trim();
  if (!value) return;
  autoCompleteFromOperation(value);
  operationInput.value = "";
});

render();
