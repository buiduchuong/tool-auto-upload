const state = {
  settings: {},
  descriptions: {},
  videos: { youtube: [], tiktok: [], facebook: [], instagram: [], zernio: [] },
  selected: { youtube: "", tiktok: "", facebook: "", instagram: "", zernio: "" },
  jobs: {},
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 2600);
}

function getNested(object, path) {
  return path.split(".").reduce((value, key) => (value ? value[key] : undefined), object);
}

function setNested(object, path, value) {
  const keys = path.split(".");
  let cursor = object;
  keys.slice(0, -1).forEach((key) => {
    cursor[key] = cursor[key] || {};
    cursor = cursor[key];
  });
  cursor[keys[keys.length - 1]] = value;
}

function accountGroup(platform) {
  return state.settings.accounts?.[platform] || { selected: "", items: [] };
}

function syncAccountFromForm(settings, platform, accountId) {
  const group = settings.accounts?.[platform];
  const selected = (group?.items || []).find((account) => account.id === accountId);
  if (!selected) return;

  const uploadDir = getNested(settings, `${platform}.upload_dir`);
  if (uploadDir) selected.upload_dir = uploadDir;

  if (platform === "facebook") {
    ["mode", "target_url", "page_id", "api_version"].forEach((key) => {
      const value = getNested(settings, `facebook.${key}`);
      if (value !== undefined) selected[key] = value;
    });
    const pageToken = getNested(settings, "facebook.page_token");
    if (String(pageToken || "").trim()) selected.page_token = pageToken;
  }
}

function collectSettings() {
  const settings = JSON.parse(JSON.stringify(state.settings || {}));
  $$("[data-setting]").forEach((input) => {
    const value = input.type === "checkbox" ? input.checked : input.value;
    setNested(settings, input.dataset.setting, value);
  });
  $$("[data-account-select]").forEach((select) => {
    const platform = select.dataset.accountSelect;
    settings.accounts = settings.accounts || {};
    settings.accounts[platform] = settings.accounts[platform] || {};
    const previousSelected = settings.accounts[platform].selected || select.value;
    syncAccountFromForm(settings, platform, previousSelected);
    settings.accounts[platform].selected = select.value;
  });
  return settings;
}

function collectDescriptions() {
  const descriptions = {};
  $$("[data-description]").forEach((input) => {
    descriptions[input.dataset.description] = input.value;
  });
  return descriptions;
}

async function api(path, body) {
  const options = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "Co loi xay ra");
  }
  return data;
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDate(stamp) {
  return new Date(stamp * 1000).toLocaleString("vi-VN");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function renderVideos(platform) {
  const list = $(`#${platform}Videos`);
  const rows = state.videos[platform] || [];
  $(`#${platform}Count`).textContent = `${rows.length} video`;
  list.innerHTML = "";
  if (!rows.length) {
    list.innerHTML = `<p class="hint">Chua co video trong thu muc account nay.</p>`;
    return;
  }
  rows.forEach((video) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `video-item ${state.selected[platform] === video.path ? "selected" : ""}`;
    item.innerHTML = `
      <span>
        <span class="video-name">${escapeHtml(video.name)}</span>
        <span class="video-meta">${formatSize(video.size)} · ${formatDate(video.modified)}</span>
      </span>
      <span class="pill">Chon</span>
    `;
    item.addEventListener("click", () => {
      state.selected[platform] = video.path;
      renderVideos(platform);
    });
    list.appendChild(item);
  });
}

function renderAccounts(platform) {
  const group = accountGroup(platform);
  const select = $(`[data-account-select="${platform}"]`);
  const list = $(`#${platform}AccountList`);
  if (!select || !list) return;
  select.innerHTML = "";
  (group.items || []).forEach((account) => {
    const option = document.createElement("option");
    option.value = account.id;
    option.textContent = account.name || account.id;
    select.appendChild(option);
  });
  select.value = group.selected || group.items?.[0]?.id || "";
  list.innerHTML = "";
  (group.items || []).forEach((account) => {
    const row = document.createElement("label");
    row.className = "account-row";
    row.innerHTML = `
      <input type="checkbox" data-sequence-account="${platform}" value="${escapeHtml(account.id)}" checked />
      <span>
        <strong>${escapeHtml(account.name || account.id)}</strong>
        <small>${escapeHtml(account.profile_dir || "")} · port ${escapeHtml(account.debug_port || "")}</small>
      </span>
    `;
    list.appendChild(row);
  });
  const current = (group.items || []).find((account) => account.id === select.value);
  const uploadInput = $(`[data-setting="${platform}.upload_dir"]`);
  if (current?.upload_dir && uploadInput) {
    uploadInput.value = current.upload_dir;
  }
  if (platform === "facebook" && (group.items || []).length > 1 && current) {
    ["mode", "target_url", "page_id", "api_version"].forEach((key) => {
      const input = $(`[data-setting="facebook.${key}"]`);
      if (input && current[key] !== undefined) input.value = current[key];
    });
  }
}

function renderForm() {
  $$("[data-setting]").forEach((input) => {
    const value = getNested(state.settings, input.dataset.setting);
    if (input.type === "checkbox") input.checked = Boolean(value);
    else input.value = value ?? "";
  });
  $$("[data-description]").forEach((input) => {
    input.value = state.descriptions[input.dataset.description] ?? "";
  });
  const tokenSaved = getNested(state.settings, "facebook.page_token_saved");
  $("#facebookTokenHint").textContent = tokenSaved
    ? "Da co token Facebook duoc luu. O token de trong se giu token cu."
    : "Chua co token Facebook duoc luu.";
  const zernioKeySaved = getNested(state.settings, "zernio.api_key_saved");
  $("#zernioKeyHint").textContent = zernioKeySaved
    ? "Da co API key Zernio duoc luu. De trong se giu key cu. Co the luu nhieu key cach nhau bang dau phay."
    : "Chua co API key Zernio duoc luu. Co the nhap nhieu key cach nhau bang dau phay.";
  ["youtube", "tiktok", "facebook", "instagram"].forEach(renderAccounts);
}

function renderJobs() {
  const jobs = state.jobs || {};
  ["youtube", "tiktok", "facebook", "instagram", "zernio", "download"].forEach((group) => {
    const item = jobs.groups?.[group] || {};
    const log = jobs.logs?.[group] || "";
    const pre = $(`#log_${group}`);
    if (pre && pre.textContent !== log) {
      pre.textContent = log;
      pre.scrollTop = pre.scrollHeight;
    }
    $$(`[data-action^="${group}."], [data-sequence="${group}"]`).forEach((button) => {
      button.disabled = Boolean(item.running);
    });
    const actionStatus = $(`#${group}ActionStatus`);
    if (actionStatus) {
      actionStatus.className = "action-status";
      if (item.running) {
        actionStatus.textContent = "Đang chạy...";
        actionStatus.classList.add("running");
      } else if (item.exit_code === 0) {
        actionStatus.textContent = "Đã hoàn thành.";
        actionStatus.classList.add("success");
      } else if (item.exit_code !== null && item.exit_code !== undefined) {
        actionStatus.textContent = `Thất bại (mã ${item.exit_code}). Mở tab Log để xem chi tiết.`;
        actionStatus.classList.add("error");
      } else {
        actionStatus.textContent = "";
      }
    }
  });
  const status = $("#toolStatus");
  if (status) {
    status.innerHTML = ["youtube", "tiktok", "facebook", "instagram", "zernio", "download"].map((group) => {
      const item = jobs.groups?.[group] || {};
      const text = item.running ? "Dang chay" : item.exit_code === null ? "Dang cho" : `Xong, ma ${item.exit_code}`;
      return `<div class="status-card"><strong>${group.toUpperCase()}</strong><span>${text}</span></div>`;
    }).join("");
  }
}

async function loadState() {
  const data = await api("/api/state");
  state.settings = data.settings;
  state.descriptions = data.descriptions;
  state.videos = data.videos;
  state.jobs = data.jobs;
  $("#baseDir").textContent = data.base_dir;
  renderForm();
  ["youtube", "tiktok", "facebook", "instagram", "zernio"].forEach(renderVideos);
  $("#toolStatus").innerHTML = `
    <div class="status-card"><strong>yt-dlp</strong><span>${data.tools.yt_dlp ? "Da co" : "Thieu file"}</span></div>
    <div class="status-card"><strong>ffmpeg</strong><span>${data.tools.ffmpeg ? "Da co" : "Thieu file"}</span></div>
  `;
  renderJobs();
}

async function pollJobs() {
  try {
    const data = await api("/api/jobs");
    state.jobs = data;
    renderJobs();
  } catch (error) {
    console.warn(error);
  }
}

async function saveAll() {
  await api("/api/settings", { settings: collectSettings() });
  await api("/api/descriptions", { descriptions: collectDescriptions() });
  toast("Da luu cau hinh.");
  await loadState();
}

function nextPort(platform, items) {
  const defaults = { youtube: 9222, tiktok: 9223, facebook: 9224, instagram: 9225 };
  const used = (items || []).map((account) => Number(account.debug_port || 0));
  let port = defaults[platform] || 9300;
  while (used.includes(port)) port += 10;
  return port;
}

function slug(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "account";
}

async function addAccount(platform) {
  const name = prompt(`Ten account ${platform}:`);
  if (!name) return;
  const settings = collectSettings();
  const group = settings.accounts[platform];
  const items = group.items || [];
  let id = `${platform}_${slug(name)}`;
  let index = 2;
  while (items.some((account) => account.id === id)) {
    id = `${platform}_${slug(name)}_${index}`;
    index += 1;
  }
  const account = {
    id,
    name,
    profile_dir: `accounts/${platform}/${id}/chrome-profile`,
    debug_port: nextPort(platform, items),
    upload_dir: getNested(settings, `${platform}.upload_dir`) || "videos",
  };
  if (platform === "facebook") {
    account.mode = getNested(settings, "facebook.mode") || "browser";
    account.target_url = getNested(settings, "facebook.target_url") || "https://www.facebook.com";
    account.page_id = "";
    account.page_token = "";
    account.api_version = getNested(settings, "facebook.api_version") || "v23.0";
  }
  items.push(account);
  group.items = items;
  group.selected = id;
  await api("/api/settings", { settings });
  toast("Da them account. Hay mo Chrome dang nhap account moi.");
  await loadState();
}

async function runAction(value) {
  const [platform, action] = value.split(".");
  const actionStatus = $(`#${platform}ActionStatus`);
  if (actionStatus) {
    actionStatus.textContent = "Đang gửi lệnh...";
    actionStatus.className = "action-status running";
  }
  const payload = {
    platform,
    action,
    settings: collectSettings(),
    descriptions: collectDescriptions(),
  };
  if (action === "upload_selected") {
    payload.video = state.selected[platform];
  }
  if (["youtube", "tiktok", "facebook", "instagram"].includes(platform)) {
    payload.account_id = accountGroup(platform).selected;
  }
  if (platform === "download") {
    payload.platform = "download";
    payload.action = "start";
    payload.urls = $("#downloadUrls").value;
  }
  await api("/api/action", payload);
  toast("Da bat dau chay.");
  await pollJobs();
}

async function runSequence(platform) {
  const accountIds = $$(`[data-sequence-account="${platform}"]:checked`).map((input) => input.value);
  if (!accountIds.length) {
    toast("Hay tick it nhat mot account.");
    return;
  }
  await api("/api/action", {
    platform,
    action: "upload_sequence",
    account_ids: accountIds,
    settings: collectSettings(),
    descriptions: collectDescriptions(),
  });
  toast("Da bat dau upload lan luot.");
  await pollJobs();
}

async function deleteSelectedVideo(platform) {
  const path = state.selected[platform];
  if (!path) {
    toast("Hay chon video can xoa.");
    return;
  }
  const video = (state.videos[platform] || []).find((item) => item.path === path);
  const name = video?.name || path;
  if (!confirm(`Xoa video nay khoi thu muc upload?\n\n${name}\n\nMac dinh file se duoc chuyen vao deleted_videos.`)) {
    return;
  }
  await api("/api/delete-video", { path, permanent: false });
  state.selected[platform] = "";
  toast("Da chuyen video vao deleted_videos.");
  await loadState();
}

function wireEvents() {
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".tab, .page").forEach((el) => el.classList.remove("active"));
      tab.classList.add("active");
      $(`#${tab.dataset.tab}`).classList.add("active");
    });
  });
  $("#refreshBtn").addEventListener("click", () => loadState().then(() => toast("Da lam moi.")));
  $("#saveAllBtn").addEventListener("click", () => saveAll().catch((error) => toast(error.message)));
  $$("[data-action]").forEach((button) => {
    button.addEventListener("click", () => runAction(button.dataset.action).catch((error) => toast(error.message)));
  });
  $$("[data-sequence]").forEach((button) => {
    button.addEventListener("click", () => runSequence(button.dataset.sequence).catch((error) => toast(error.message)));
  });
  $$("[data-delete-selected]").forEach((button) => {
    button.addEventListener("click", () => deleteSelectedVideo(button.dataset.deleteSelected).catch((error) => toast(error.message)));
  });
  $$("[data-add-account]").forEach((button) => {
    button.addEventListener("click", () => addAccount(button.dataset.addAccount).catch((error) => toast(error.message)));
  });
  $$("[data-account-select]").forEach((select) => {
    select.addEventListener("change", async () => {
      try {
        await api("/api/settings", { settings: collectSettings() });
        await loadState();
      } catch (error) {
        toast(error.message);
      }
    });
  });
  $$("[data-stop]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api("/api/stop", { group: button.dataset.stop || null });
      toast("Da gui lenh dung.");
      await pollJobs();
    });
  });
}

wireEvents();
loadState().catch((error) => toast(error.message));
setInterval(pollJobs, 1500);
