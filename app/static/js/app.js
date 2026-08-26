/**
 * Telegram Downloader Main Client Application
 */
window.App = (function () {
  let currentUser = null;
  let sseSource = null;
  let activePickerTargetId = null;
  let pickerCurrentPath = "";
  let currentDownloadsFilter = "ALL";
  let activeDownloadsCache = {};
  let updateInterval = null;

  // Initialize on DOM load
  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    setupRouter();
    await checkAuthAndSetup();
  }

  // Router based on window.location.hash
  function setupRouter() {
    window.addEventListener("hashchange", handleRouteChange);
    handleRouteChange();
  }

  function handleRouteChange() {
    const hash = window.location.hash.replace("#", "") || "dashboard";
    switchView(hash);
  }

  function switchView(viewName) {
    document.querySelectorAll(".view-pane").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

    const targetView = document.getElementById(`view-${viewName}`);
    const targetNav = document.querySelector(`.nav-item[data-view="${viewName}"]`);

    if (targetView) targetView.classList.add("active");
    if (targetNav) targetNav.classList.add("active");

    const headingEl = document.getElementById("page-heading");
    if (headingEl) {
      headingEl.innerText = viewName.charAt(0).toUpperCase() + viewName.slice(1);
    }

    // Refresh view-specific data
    if (currentUser) {
      if (viewName === "dashboard") loadDashboard();
      else if (viewName === "telegram") loadTelegram();
      else if (viewName === "downloads") loadDownloads();
      else if (viewName === "storage") loadStorage();
      else if (viewName === "sources") loadSources();
      else if (viewName === "jellyfin") loadJellyfin();
      else if (viewName === "logs") loadLogs();
      else if (viewName === "settings") loadSettings();
      else if (viewName === "system") loadSystem();
    }
  }

  // API Helper
  async function apiCall(endpoint, method = "GET", body = null) {
    const headers = { "Accept": "application/json" };
    const opts = { method, headers };

    if (body) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }

    try {
      const resp = await fetch(endpoint, opts);
      let data = {};
      try {
        data = await resp.json();
      } catch (e) {
        throw new Error("Server returned non-JSON response.");
      }

      if (!resp.ok) {
        if (resp.status === 401 && !endpoint.includes("/api/auth/")) {
          showLoginModal();
        }
        throw new Error(data.message || data.detail || `Request failed with HTTP ${resp.status}`);
      }
      return data;
    } catch (err) {
      throw err;
    }
  }

  // Auth & Initial Setup Check
  async function checkAuthAndSetup() {
    try {
      showLoading("Checking server state...");
      const setupStatus = await apiCall("/api/auth/setup-status");
      hideLoading();

      // Check current session or default admin
      try {
        const user = await apiCall("/api/auth/me");
        currentUser = user;
        document.getElementById("user-display-name").innerText = user.username;
        await initDashboard();
      } catch (e) {
        if (setupStatus.is_setup_completed) {
          showLoginModal();
        } else {
          // Unconfigured state: allow full access to dashboard and settings
          currentUser = { username: "admin" };
          document.getElementById("user-display-name").innerText = "admin";
          await initDashboard();
        }
      }

      updateConfigBanner(setupStatus);
    } catch (e) {
      hideLoading();
      toast("Error contacting server: " + e.message, "error");
    }
  }

  function updateConfigBanner(status) {
    const banner = document.getElementById("dash-config-banner");
    const msg = document.getElementById("dash-config-msg");
    if (!banner) return;

    if (!status.is_telegram_configured && !status.download_dir) {
      banner.classList.remove("hidden");
      if (msg) msg.innerText = "Telegram API credentials and Download storage folder are not configured yet.";
    } else if (!status.is_telegram_configured) {
      banner.classList.remove("hidden");
      if (msg) msg.innerText = "Telegram API credentials are not configured yet. Enter API ID & Hash in the Telegram tab.";
    } else if (!status.is_telegram_authenticated) {
      banner.classList.remove("hidden");
      if (msg) msg.innerText = "Telegram account is not connected yet. Sign in via phone/code in the Telegram tab.";
    } else if (!status.download_dir) {
      banner.classList.remove("hidden");
      if (msg) msg.innerText = "Download storage directory is not selected yet. Choose a download folder in the Storage tab.";
    } else {
      banner.classList.add("hidden");
    }
  }

  function showLoginModal() {
    document.getElementById("login-modal").classList.remove("hidden");
  }

  async function handleLogin(e) {
    e.preventDefault();
    const user = document.getElementById("login-username").value.trim();
    const pass = document.getElementById("login-password").value;
    const errEl = document.getElementById("login-error");
    errEl.classList.add("hidden");

    try {
      showLoading("Authenticating...");
      const res = await apiCall("/api/auth/login", "POST", { username: user, password: pass });
      hideLoading();
      currentUser = { username: res.username };
      document.getElementById("user-display-name").innerText = res.username;
      document.getElementById("login-modal").classList.add("hidden");
      toast("Signed in successfully!", "success");
      await initDashboard();
    } catch (err) {
      hideLoading();
      errEl.innerText = err.message;
      errEl.classList.remove("hidden");
    }
  }

  async function handleSetAdminPassword(e) {
    e.preventDefault();
    const user = document.getElementById("set-admin-user").value.trim() || "admin";
    const pass = document.getElementById("set-admin-pass").value;
    if (!pass || pass.length < 4) {
      toast("Password must be at least 4 characters long.", "error");
      return;
    }

    try {
      showLoading("Saving administrator credentials...");
      const res = await apiCall("/api/auth/set-password", "POST", { username: user, password: pass });
      hideLoading();
      toast(res.message || "Administrator password saved!", "success");
      document.getElementById("set-admin-pass").value = "";
      currentUser = { username: res.username };
      document.getElementById("user-display-name").innerText = res.username;
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  async function logout() {
    try {
      await apiCall("/api/auth/logout", "POST");
      currentUser = null;
      if (sseSource) sseSource.close();
      if (updateInterval) clearInterval(updateInterval);
      showLoginModal();
    } catch (e) {
      window.location.reload();
    }
  }

  async function initDashboard() {
    loadDashboard();
    setupSSE();
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(loadDashboard, 5000);
  }

  // Real-time Event Stream (SSE)
  function setupSSE() {
    if (sseSource) sseSource.close();
    try {
      sseSource = new EventSource("/api/logs/stream");

      sseSource.addEventListener("log", (e) => {
        const entry = JSON.parse(e.data);
        appendLogLine(entry);
      });

      sseSource.addEventListener("download_progress", (e) => {
        const progress = JSON.parse(e.data);
        updateActiveDownloadRow(progress);
      });

      sseSource.onerror = () => {
        // SSE auto-reconnects
      };
    } catch (e) {
      console.warn("SSE not available:", e);
    }
  }

  // View: Dashboard
  async function loadDashboard() {
    try {
      const stats = await apiCall("/api/dashboard/stats");

      // Update counters
      document.getElementById("dash-active-count").innerText = stats.downloads.downloading;
      document.getElementById("dash-completed-count").innerText = stats.downloads.completed;
      document.getElementById("dash-speed").innerText = stats.downloads.current_speed_formatted;
      document.getElementById("header-speed").innerText = "⚡ " + stats.downloads.current_speed_formatted;

      if (stats.storage.drive) {
        document.getElementById("dash-free-space").innerText = stats.storage.drive.free_formatted;
      }
      document.getElementById("dash-download-dir").innerText = stats.storage.download_dir || "Not configured";
      document.getElementById("dash-sources-count").innerText = `${stats.sources.enabled} of ${stats.sources.total} active`;
      document.getElementById("dash-uptime").innerText = stats.system.uptime_formatted;

      updateConfigBanner({
        is_telegram_configured: stats.telegram.is_configured,
        is_telegram_authenticated: stats.telegram.is_authorized,
        download_dir: stats.storage.download_dir,
      });

      // Header pills
      const tgStatusEl = document.getElementById("header-tg-status");
      const tgDot = tgStatusEl.querySelector(".status-dot");
      const tgText = tgStatusEl.querySelector("span:last-child");
      const tgBadge = document.getElementById("nav-tg-badge");

      if (stats.telegram.is_authorized) {
        tgDot.className = "status-dot dot-green";
        tgText.innerText = `Telegram: @${stats.telegram.username || stats.telegram.first_name || 'Connected'}`;
        tgBadge.className = "badge badge-success";
        tgBadge.innerText = "Connected";
        document.getElementById("dash-tg-badge").className = "badge badge-success";
        document.getElementById("dash-tg-badge").innerText = "Connected";
      } else {
        tgDot.className = "status-dot dot-yellow";
        tgText.innerText = `Telegram: ${stats.telegram.status}`;
        tgBadge.className = "badge badge-warning";
        tgBadge.innerText = stats.telegram.status;
        document.getElementById("dash-tg-badge").className = "badge badge-warning";
        document.getElementById("dash-tg-badge").innerText = stats.telegram.status;
      }

      document.getElementById("nav-dl-badge").innerText = stats.downloads.downloading + stats.downloads.queued;

      // Active downloads snippet
      renderDashActiveDownloads(stats.downloads);

      // Errors snippet
      const errsContainer = document.getElementById("dash-recent-errors-list");
      if (stats.recent_errors && stats.recent_errors.length > 0) {
        errsContainer.innerHTML = stats.recent_errors.map(err => `
          <div class="alert alert-danger mb-2">
            <strong>${err.filename}:</strong> ${err.error_message}
            <small class="d-block text-dim">${err.created_at}</small>
          </div>
        `).join("");
      } else {
        errsContainer.innerHTML = '<p class="empty-state">No recent errors recorded.</p>';
      }

    } catch (e) {
      console.warn("Error refreshing dashboard:", e);
    }
  }

  async function renderDashActiveDownloads(dlStats) {
    const container = document.getElementById("dash-active-downloads-list");
    if (dlStats.downloading === 0 && dlStats.queued === 0) {
      container.innerHTML = '<p class="empty-state">No active downloads in progress.</p>';
      return;
    }

    try {
      const activeJobs = await apiCall("/api/downloads?status=DOWNLOADING&limit=5");
      if (activeJobs.length === 0) {
        container.innerHTML = '<p class="empty-state">No active downloads in progress.</p>';
        return;
      }

      container.innerHTML = activeJobs.map(job => `
        <div class="job-card mb-3 p-3" style="background: var(--bg-input); border-radius: var(--radius-sm); border: 1px solid var(--border);">
          <div class="d-flex justify-content-between mb-1">
            <strong>${job.sanitized_filename}</strong>
            <span class="badge badge-info">${job.progress_percent}%</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: ${job.progress_percent}%"></div>
          </div>
          <div class="d-flex justify-content-between mt-1 text-dim" style="font-size: 0.75rem;">
            <span>${job.downloaded_formatted} / ${job.file_size_formatted}</span>
            <span>⚡ ${job.speed_formatted}</span>
          </div>
        </div>
      `).join("");
    } catch (e) {
      // Ignore
    }
  }

  // View: Telegram
  async function loadTelegram() {
    try {
      const tg = await apiCall("/api/telegram/status");
      const dot = document.getElementById("tg-status-dot");
      const text = document.getElementById("tg-status-text");
      const userText = document.getElementById("tg-user-text");

      text.innerText = tg.status;
      if (tg.is_authorized) {
        dot.className = "status-dot dot-green";
        userText.innerText = `${tg.first_name || ''} (@${tg.username || tg.phone || tg.user_id})`;
      } else {
        dot.className = "status-dot dot-yellow";
        userText.innerText = "None (Not Authenticated)";
      }

      const settings = await apiCall("/api/settings");
      if (settings.telegram_phone) {
        document.getElementById("tg-cfg-phone").value = settings.telegram_phone;
      }
    } catch (e) {
      toast("Error loading Telegram status: " + e.message, "error");
    }
  }

  async function handleTelegramConfig(e) {
    e.preventDefault();
    const apiIdStr = document.getElementById("tg-cfg-api-id").value.trim();
    const apiHash = document.getElementById("tg-cfg-api-hash").value.trim();
    const phone = document.getElementById("tg-cfg-phone").value.trim();

    const apiId = parseInt(apiIdStr, 10);
    if (isNaN(apiId) || apiId < 1 || apiId > 2147483647) {
      toast("Invalid Telegram API ID. Must be a 32-bit signed integer (1 to 2147483647).", "error");
      return;
    }

    try {
      showLoading("Connecting to Telegram MTProto...");
      const res = await apiCall("/api/telegram/config", "POST", {
        api_id: apiId,
        api_hash: apiHash,
        phone: phone,
      });
      hideLoading();

      if (res.status === "CONNECTED") {
        toast("Telegram connected and authorized!", "success");
        loadTelegram();
      } else if (res.status === "WAITING_CODE") {
        toast(res.message, "info");
        openTelegramAuthModal(false);
      }
    } catch (err) {
      hideLoading();
      toast(err.message, "error");
    }
  }

  function openTelegramAuthModal(is2FA = false) {
    document.getElementById("tg-auth-modal").classList.remove("hidden");
    document.getElementById("tg-otp-pane").classList.toggle("hidden", is2FA);
    document.getElementById("tg-2fa-pane").classList.toggle("hidden", !is2FA);
  }

  async function submitTelegramCode() {
    const code = document.getElementById("tg-auth-code").value.trim();
    if (!code) {
      toast("Please enter the verification code.", "error");
      return;
    }

    try {
      showLoading("Verifying OTP code...");
      const res = await apiCall("/api/telegram/submit-code", "POST", { phone_code: code });
      hideLoading();

      if (res.status === "CONNECTED") {
        closeModal("tg-auth-modal");
        toast("Telegram successfully authenticated!", "success");
        loadTelegram();
      } else if (res.status === "WAITING_PASSWORD") {
        openTelegramAuthModal(true);
      }
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  async function submitTelegramPassword() {
    const pwd = document.getElementById("tg-auth-password").value;
    if (!pwd) {
      toast("Please enter your 2FA password.", "error");
      return;
    }

    try {
      showLoading("Verifying 2FA password...");
      const res = await apiCall("/api/telegram/submit-password", "POST", { password: pwd });
      hideLoading();

      if (res.status === "CONNECTED") {
        closeModal("tg-auth-modal");
        toast("Telegram 2FA authentication verified!", "success");
        loadTelegram();
      }
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  async function logoutTelegram() {
    if (!confirm("Are you sure you want to log out from Telegram? This will remove your active session.")) return;
    try {
      showLoading("Logging out from Telegram...");
      await apiCall("/api/telegram/logout", "POST");
      hideLoading();
      toast("Telegram session terminated.", "info");
      loadTelegram();
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  // View: Downloads
  async function loadDownloads() {
    try {
      // Bind tab filters
      document.querySelectorAll(".filter-tab").forEach(tab => {
        tab.onclick = () => {
          document.querySelectorAll(".filter-tab").forEach(t => t.classList.remove("active"));
          tab.classList.add("active");
          currentDownloadsFilter = tab.dataset.filter;
          loadDownloads();
        };
      });

      const stats = await apiCall("/api/downloads/stats");
      document.getElementById("tab-cnt-all").innerText = stats.total;
      document.getElementById("tab-cnt-dl").innerText = stats.downloading;
      document.getElementById("tab-cnt-q").innerText = stats.queued;
      document.getElementById("tab-cnt-comp").innerText = stats.completed;
      document.getElementById("tab-cnt-fail").innerText = stats.failed;
      document.getElementById("tab-cnt-retry").innerText = stats.retrying;

      const filterParam = currentDownloadsFilter === "ALL" ? "" : `&status=${currentDownloadsFilter}`;
      const downloads = await apiCall(`/api/downloads?limit=100${filterParam}`);
      const tbody = document.getElementById("downloads-tbody");

      if (downloads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No downloads matching filter.</td></tr>';
        return;
      }

      tbody.innerHTML = downloads.map(d => {
        let badgeClass = "badge-info";
        if (d.status === "COMPLETED") badgeClass = "badge-success";
        else if (d.status === "FAILED") badgeClass = "badge-danger";
        else if (d.status === "CANCELLED") badgeClass = "badge-warning";
        else if (d.status === "RETRYING") badgeClass = "badge-warning";

        let actions = "";
        if (d.status === "DOWNLOADING" || d.status === "QUEUED" || d.status === "RETRYING") {
          actions += `<button class="btn btn-sm btn-danger" onclick="window.App.cancelDownload(${d.id})">Cancel</button> `;
        }
        if (d.status === "FAILED" || d.status === "CANCELLED") {
          actions += `<button class="btn btn-sm btn-secondary" onclick="window.App.retryDownload(${d.id})">Retry</button> `;
        }
        actions += `<button class="btn btn-sm btn-secondary" onclick="window.App.deleteDownload(${d.id})">Delete</button>`;

        return `
          <tr id="dl-row-${d.id}">
            <td>
              <div class="text-bold">${d.sanitized_filename}</div>
              ${d.error_message ? `<small class="text-danger">${d.error_message}</small>` : ''}
            </td>
            <td>${d.source_title || 'Telegram'}</td>
            <td>${d.file_size_formatted}</td>
            <td><span class="badge ${badgeClass}">${d.status}</span></td>
            <td>
              <div class="progress-bar-bg" style="width: 120px;">
                <div class="progress-bar-fill" style="width: ${d.progress_percent}%"></div>
              </div>
              <small class="text-dim">${d.progress_percent}%</small>
            </td>
            <td>
              <div>${d.speed_formatted}</div>
              ${d.eta_seconds ? `<small class="text-dim">ETA: ${d.eta_seconds}s</small>` : ''}
            </td>
            <td>${actions}</td>
          </tr>
        `;
      }).join("");

    } catch (e) {
      toast("Error loading downloads: " + e.message, "error");
    }
  }

  function updateActiveDownloadRow(progress) {
    const row = document.getElementById(`dl-row-${progress.id}`);
    if (row) {
      const fill = row.querySelector(".progress-bar-fill");
      if (fill) fill.style.width = `${progress.progress_percent}%`;
    }
  }

  async function cancelDownload(id) {
    try {
      await apiCall(`/api/downloads/${id}/cancel`, "POST");
      toast(`Download #${id} cancelled.`, "info");
      loadDownloads();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function retryDownload(id) {
    try {
      await apiCall(`/api/downloads/${id}/retry`, "POST");
      toast(`Download #${id} re-queued.`, "success");
      loadDownloads();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function deleteDownload(id) {
    try {
      await apiCall(`/api/downloads/${id}`, "DELETE");
      toast(`Download #${id} removed.`, "info");
      loadDownloads();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function clearCompletedDownloads() {
    if (!confirm("Clear all completed and cancelled download history?")) return;
    try {
      const res = await apiCall("/api/downloads/clear-completed", "POST");
      toast(res.message, "success");
      loadDownloads();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  // View: Storage
  async function loadStorage() {
    try {
      const res = await apiCall("/api/storage/drives");
      document.getElementById("storage-current-dir").value = res.current_download_dir || "Not configured";

      const grid = document.getElementById("storage-drives-list");
      grid.innerHTML = res.drives.map(d => `
        <div class="drive-card">
          <div class="drive-header">
            <strong>${d.mountpoint} (${d.fstype})</strong>
            <span class="badge ${d.is_writable ? 'badge-success' : 'badge-danger'}">
              ${d.is_writable ? 'Writable' : 'Read Only'}
            </span>
          </div>
          <div class="progress-bar-bg mt-2">
            <div class="progress-bar-fill" style="width: ${d.percent_used}%"></div>
          </div>
          <div class="d-flex justify-content-between mt-2 text-dim" style="font-size: 0.8rem;">
            <span>Used: ${d.percent_used}%</span>
            <span>Free: ${d.free_formatted} / Total: ${d.total_formatted}</span>
          </div>
        </div>
      `).join("");
    } catch (e) {
      toast("Error loading storage info: " + e.message, "error");
    }
  }

  // Folder Picker Component
  async function openFolderPicker(targetInputId, saveImmediately = false) {
    activePickerTargetId = targetInputId;
    pickerCurrentPath = "";
    document.getElementById("folder-picker-modal").classList.remove("hidden");
    await refreshFolderList("");
  }

  async function refreshFolderList(path) {
    try {
      const res = await apiCall("/api/storage/browse", "POST", { path });
      pickerCurrentPath = res.current_path || "";
      document.getElementById("picker-current-path").innerText = pickerCurrentPath || "Windows Drives";
      document.getElementById("picker-up-btn").style.display = res.parent_path !== undefined ? "inline-block" : "none";
      document.getElementById("picker-up-btn").dataset.parent = res.parent_path || "";

      const listEl = document.getElementById("picker-folder-list");
      if (res.drives) {
        listEl.innerHTML = res.drives.map(d => `
          <div class="folder-item" onclick="window.App.navigateToFolder('${escapeJs(d.path)}')">
            <span>💽</span> <strong>${d.label}</strong>
          </div>
        `).join("");
      } else if (res.directories) {
        if (res.directories.length === 0) {
          listEl.innerHTML = '<div class="p-3 text-muted">No subdirectories found.</div>';
        } else {
          listEl.innerHTML = res.directories.map(dir => `
            <div class="folder-item" onclick="window.App.navigateToFolder('${escapeJs(dir.path)}')">
              <span>📁</span> ${dir.name}
            </div>
          `).join("");
        }
      }
    } catch (e) {
      toast("Error listing folders: " + e.message, "error");
    }
  }

  function navigateToFolder(path) {
    refreshFolderList(path);
  }

  function navigateFolderUp() {
    const parent = document.getElementById("picker-up-btn").dataset.parent;
    refreshFolderList(parent);
  }

  async function selectCurrentFolder() {
    if (!pickerCurrentPath) {
      toast("Please navigate into a specific folder.", "error");
      return;
    }

    if (activePickerTargetId) {
      const targetInput = document.getElementById(activePickerTargetId);
      if (targetInput) targetInput.value = pickerCurrentPath;

      // If updating main storage view, save immediately
      if (activePickerTargetId === "storage-current-dir") {
        try {
          await apiCall("/api/storage/select", "POST", { download_dir: pickerCurrentPath });
          toast("Storage directory updated!", "success");
        } catch (e) {
          toast(e.message, "error");
        }
      }
    }
    closeModal("folder-picker-modal");
  }

  // View: Sources
  async function loadSources() {
    try {
      const sources = await apiCall("/api/sources");
      const listEl = document.getElementById("sources-list");

      if (sources.length === 0) {
        listEl.innerHTML = '<p class="empty-state">No Telegram sources registered yet.</p>';
        return;
      }

      listEl.innerHTML = sources.map(s => `
        <div class="card mb-3">
          <div class="card-header">
            <div>
              <strong>${s.title}</strong>
              <small class="text-dim font-mono d-block">ID: ${s.telegram_id} ${s.username ? `(@${s.username})` : ''}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
              <label class="form-check mb-0">
                <input type="checkbox" class="form-checkbox" ${s.is_enabled ? 'checked' : ''} onchange="window.App.toggleSource(${s.id}, this.checked)">
                <span>${s.is_enabled ? 'Active' : 'Disabled'}</span>
              </label>
              <button class="btn btn-sm btn-danger" onclick="window.App.deleteSource(${s.id})">Remove</button>
            </div>
          </div>
          <div class="card-body">
            <div class="d-flex flex-wrap gap-2">
              <span class="badge ${s.download_videos ? 'badge-info' : 'badge-secondary'}">Videos: ${s.download_videos ? 'ON' : 'OFF'}</span>
              <span class="badge ${s.download_documents ? 'badge-info' : 'badge-secondary'}">Docs: ${s.download_documents ? 'ON' : 'OFF'}</span>
              <span class="badge ${s.download_audio ? 'badge-info' : 'badge-secondary'}">Audio: ${s.download_audio ? 'ON' : 'OFF'}</span>
              <span class="badge ${s.download_archives ? 'badge-info' : 'badge-secondary'}">Archives: ${s.download_archives ? 'ON' : 'OFF'}</span>
              <span class="badge ${s.download_images ? 'badge-info' : 'badge-secondary'}">Images: ${s.download_images ? 'ON' : 'OFF'}</span>
            </div>
            ${s.custom_subfolder ? `<div class="mt-2 text-dim font-mono" style="font-size: 0.8rem;">Subfolder: /${s.custom_subfolder}</div>` : ''}
          </div>
        </div>
      `).join("");
    } catch (e) {
      toast("Error loading sources: " + e.message, "error");
    }
  }

  async function testSourceLookup() {
    const id = document.getElementById("src-telegram-id").value.trim();
    if (!id) {
      toast("Please enter a Telegram ID or link first.", "error");
      return;
    }
    const resEl = document.getElementById("src-lookup-result");
    resEl.classList.remove("hidden");
    resEl.className = "alert alert-info";
    resEl.innerText = "Resolving Telegram entity...";

    try {
      const res = await apiCall("/api/sources/test", "POST", { telegram_id: id });
      if (res.success) {
        resEl.className = "alert alert-info";
        resEl.innerHTML = `Found: <strong>${res.data.title}</strong> (${res.data.source_type})`;
        if (!document.getElementById("src-title").value) {
          document.getElementById("src-title").value = res.data.title;
        }
      } else {
        resEl.className = "alert alert-warning";
        resEl.innerText = res.message;
      }
    } catch (e) {
      resEl.className = "alert alert-danger";
      resEl.innerText = e.message;
    }
  }

  async function handleAddSource(e) {
    e.preventDefault();
    const payload = {
      telegram_id: document.getElementById("src-telegram-id").value.trim(),
      title: document.getElementById("src-title").value.trim() || null,
      custom_subfolder: document.getElementById("src-subfolder").value.trim() || null,
      download_videos: document.getElementById("src-dl-videos").checked,
      download_documents: document.getElementById("src-dl-docs").checked,
      download_audio: document.getElementById("src-dl-audio").checked,
      download_archives: document.getElementById("src-dl-archives").checked,
      download_images: document.getElementById("src-dl-images").checked,
    };

    try {
      showLoading("Adding source...");
      await apiCall("/api/sources", "POST", payload);
      hideLoading();
      closeModal("add-source-modal");
      toast("Telegram source added!", "success");
      loadSources();
    } catch (err) {
      hideLoading();
      toast(err.message, "error");
    }
  }

  async function toggleSource(id, isEnabled) {
    try {
      await apiCall(`/api/sources/${id}`, "PUT", { is_enabled: isEnabled });
      toast(`Source ${isEnabled ? 'enabled' : 'disabled'}.`, "info");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function deleteSource(id) {
    if (!confirm("Are you sure you want to remove this source from monitoring?")) return;
    try {
      await apiCall(`/api/sources/${id}`, "DELETE");
      toast("Source removed.", "info");
      loadSources();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  // Discovered Sources Component
  let discoveredSourcesData = [];

  async function openDiscoverSourcesModal() {
    openModal("discover-sources-modal");
    await loadDiscoverDialogs();
  }

  async function loadDiscoverDialogs() {
    const listContainer = document.getElementById("discover-list-container");
    const loadingEl = document.getElementById("discover-loading");
    if (!listContainer || !loadingEl) return;

    listContainer.innerHTML = "";
    loadingEl.classList.remove("hidden");

    try {
      const res = await apiCall("/api/sources/discover/all");
      discoveredSourcesData = res.sources || [];
      renderDiscoveredSources();
    } catch (e) {
      listContainer.innerHTML = `<div class="p-3 text-center text-danger">${escapeHtml(e.message)}</div>`;
    } finally {
      loadingEl.classList.add("hidden");
    }
  }

  function filterDiscoveredSources() {
    renderDiscoveredSources();
  }

  function renderDiscoveredSources() {
    const listContainer = document.getElementById("discover-list-container");
    if (!listContainer) return;

    const query = (document.getElementById("discover-search")?.value || "").toLowerCase().trim();

    const filtered = discoveredSourcesData.filter(s => 
      (s.title || "").toLowerCase().includes(query) ||
      (s.username || "").toLowerCase().includes(query) ||
      (s.telegram_id || "").includes(query)
    );

    const selectedCount = discoveredSourcesData.filter(s => s.is_monitored).length;
    const cntEl = document.getElementById("discover-selected-count");
    if (cntEl) cntEl.innerText = `${selectedCount} selected`;

    if (filtered.length === 0) {
      listContainer.innerHTML = '<div class="p-3 text-center text-muted">No matching Telegram channels or groups found.</div>';
      return;
    }

    listContainer.innerHTML = filtered.map(s => {
      let typeBadge = "badge-info";
      if (s.source_type === "CHANNEL") typeBadge = "badge-primary";
      else if (s.source_type === "SUPERGROUP") typeBadge = "badge-success";
      else if (s.source_type === "GROUP") typeBadge = "badge-warning";
      else if (s.source_type === "SAVED_MESSAGES") typeBadge = "badge-secondary";

      return `
        <label class="d-flex align-items-center gap-2 p-2 border-bottom" style="cursor: pointer; user-select: none;">
          <input type="checkbox" class="form-checkbox" ${s.is_monitored ? 'checked' : ''} onchange="window.App.onDiscoveredCheckboxChange('${escapeHtml(s.telegram_id)}', this.checked)">
          <div class="flex-grow-1">
            <strong>${escapeHtml(s.title)}</strong>
            <span class="badge ${typeBadge} ms-2" style="font-size: 0.7rem;">${escapeHtml(s.source_type)}</span>
            <small class="text-dim d-block font-mono" style="font-size: 0.75rem;">ID: ${escapeHtml(s.telegram_id)} ${s.username ? `(@${escapeHtml(s.username)})` : ''}</small>
          </div>
        </label>
      `;
    }).join("");
  }

  function onDiscoveredCheckboxChange(tid, isChecked) {
    const item = discoveredSourcesData.find(x => String(x.telegram_id) === String(tid));
    if (item) {
      item.is_monitored = isChecked;
      const count = discoveredSourcesData.filter(x => x.is_monitored).length;
      const cntEl = document.getElementById("discover-selected-count");
      if (cntEl) cntEl.innerText = `${count} selected`;
    }
  }

  function toggleAllDiscovered(select) {
    discoveredSourcesData.forEach(s => s.is_monitored = select);
    renderDiscoveredSources();
  }

  async function saveBatchDiscoveredSources() {
    try {
      showLoading("Saving monitored sources...");
      const items = discoveredSourcesData.map(s => ({
        telegram_id: s.telegram_id,
        title: s.title,
        username: s.username,
        source_type: s.source_type,
        is_monitored: Boolean(s.is_monitored),
        custom_subfolder: "movies"
      }));

      const res = await apiCall("/api/sources/batch-toggle", "POST", { items });
      hideLoading();
      closeModal("discover-sources-modal");
      toast(res.message || "Sources updated successfully!", "success");
      loadSources();
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  // View: Jellyfin
  async function loadJellyfin() {
    try {
      const cfg = await apiCall("/api/jellyfin/config");
      document.getElementById("jf-url").value = cfg.url || "";
      document.getElementById("jf-key").value = cfg.api_key || "";
      document.getElementById("jf-auto-refresh").checked = cfg.auto_refresh;
    } catch (e) {
      toast("Error loading Jellyfin config: " + e.message, "error");
    }
  }

  async function saveJellyfinConfig(e) {
    e.preventDefault();
    const payload = {
      url: document.getElementById("jf-url").value.trim() || null,
      api_key: document.getElementById("jf-key").value.trim() || null,
      auto_refresh: document.getElementById("jf-auto-refresh").checked,
    };

    try {
      showLoading("Saving Jellyfin settings...");
      await apiCall("/api/jellyfin/config", "PUT", payload);
      hideLoading();
      toast("Jellyfin configuration saved!", "success");
    } catch (err) {
      hideLoading();
      toast(err.message, "error");
    }
  }

  async function testJellyfin() {
    const payload = {
      url: document.getElementById("jf-url").value.trim() || null,
      api_key: document.getElementById("jf-key").value.trim() || null,
    };
    const statusEl = document.getElementById("jf-test-status");
    statusEl.classList.remove("hidden");
    statusEl.className = "alert alert-info";
    statusEl.innerText = "Testing Jellyfin connection...";

    try {
      const res = await apiCall("/api/jellyfin/test", "POST", payload);
      if (res.success) {
        statusEl.className = "alert alert-info";
        statusEl.innerText = `✅ ${res.message}`;
      } else {
        statusEl.className = "alert alert-danger";
        statusEl.innerText = `❌ ${res.message}`;
      }
    } catch (e) {
      statusEl.className = "alert alert-danger";
      statusEl.innerText = e.message;
    }
  }

  async function triggerJellyfinRefresh() {
    try {
      showLoading("Requesting Jellyfin scan...");
      const res = await apiCall("/api/jellyfin/refresh", "POST");
      hideLoading();
      toast(res.message, "success");
    } catch (e) {
      hideLoading();
      toast(e.message, "error");
    }
  }

  // View: Logs
  async function loadLogs() {
    const level = document.getElementById("log-level-filter").value;
    try {
      const logs = await apiCall(`/api/logs?limit=300&level=${level}`);
      const consoleEl = document.getElementById("log-console");
      consoleEl.innerHTML = "";
      logs.forEach(appendLogLine);
      consoleEl.scrollTop = consoleEl.scrollHeight;
    } catch (e) {
      toast("Error loading logs: " + e.message, "error");
    }
  }

  function appendLogLine(entry) {
    const consoleEl = document.getElementById("log-console");
    if (!consoleEl) return;
    const div = document.createElement("div");
    div.className = `log-line log-${entry.level}`;
    div.innerText = entry.formatted || `[${entry.level}] ${entry.message}`;
    consoleEl.appendChild(div);
    if (consoleEl.children.length > 500) {
      consoleEl.removeChild(consoleEl.firstChild);
    }
  }

  function downloadLogFile() {
    window.open("/api/logs/download", "_blank");
  }

  function clearLogConsole() {
    const consoleEl = document.getElementById("log-console");
    if (consoleEl) consoleEl.innerHTML = "";
  }

  // View: Settings
  async function loadSettings() {
    try {
      const s = await apiCall("/api/settings");
      document.getElementById("set-host").value = s.host;
      document.getElementById("set-port").value = s.port;
      document.getElementById("set-concurrency").value = s.max_concurrent_downloads;
      document.getElementById("set-space-threshold").value = s.free_space_threshold_mb;
      document.getElementById("set-max-retries").value = s.max_retries;
      document.getElementById("set-retry-delay").value = s.retry_delay_seconds;
    } catch (e) {
      toast("Error loading settings: " + e.message, "error");
    }
  }

  async function saveGeneralSettings(e) {
    e.preventDefault();
    const payload = {
      host: document.getElementById("set-host").value.trim(),
      port: parseInt(document.getElementById("set-port").value, 10),
      max_concurrent_downloads: parseInt(document.getElementById("set-concurrency").value, 10),
      free_space_threshold_mb: parseInt(document.getElementById("set-space-threshold").value, 10),
      max_retries: parseInt(document.getElementById("set-max-retries").value, 10),
      retry_delay_seconds: parseInt(document.getElementById("set-retry-delay").value, 10),
    };

    try {
      showLoading("Saving settings...");
      await apiCall("/api/settings", "PUT", payload);
      hideLoading();
      toast("Settings updated successfully!", "success");
    } catch (err) {
      hideLoading();
      toast(err.message, "error");
    }
  }

  // View: System
  async function loadSystem() {
    try {
      const sys = await apiCall("/api/system/status");
      document.getElementById("sys-cpu-val").innerText = `${sys.cpu_percent}%`;
      document.getElementById("sys-cpu-bar").style.width = `${sys.cpu_percent}%`;

      document.getElementById("sys-ram-val").innerText = `${sys.ram_percent}% (${sys.ram_used_formatted} / ${sys.ram_total_formatted})`;
      document.getElementById("sys-ram-bar").style.width = `${sys.ram_percent}%`;

      document.getElementById("sys-app-ver").innerText = sys.app_version;
      document.getElementById("sys-py-ver").innerText = sys.python_version;
      document.getElementById("sys-os-ver").innerText = sys.os_name;

      const settings = await apiCall("/api/settings");
      document.getElementById("sys-data-dir").innerText = settings.data_dir;
    } catch (e) {
      toast("Error loading system metrics: " + e.message, "error");
    }
  }

  // UI Utilities
  function showLoading(text = "Loading...") {
    document.getElementById("loading-text").innerText = text;
    document.getElementById("loading-overlay").classList.remove("hidden");
  }

  function hideLoading() {
    document.getElementById("loading-overlay").classList.add("hidden");
  }

  function toast(msg, type = "info") {
    const container = document.getElementById("toast-container");
    const t = document.createElement("div");
    t.className = `toast toast-${type}`;
    t.innerText = msg;
    container.appendChild(t);
    setTimeout(() => {
      t.remove();
    }, 4000);
  }

  function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
  }

  function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
  }

  function toggleSidebar() {
    document.querySelector(".sidebar").classList.toggle("open");
  }

  function escapeJs(str) {
    return (str || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  return {
    init,
    switchView,
    apiCall,
    toast,
    showLoading,
    hideLoading,
    openModal,
    closeModal,
    toggleSidebar,
    handleLogin,
    handleSetAdminPassword,
    logout,
    initDashboard,
    loadDashboard,
    loadTelegram,
    handleTelegramConfig,
    submitTelegramCode,
    submitTelegramPassword,
    logoutTelegram,
    loadDownloads,
    cancelDownload,
    retryDownload,
    deleteDownload,
    clearCompletedDownloads,
    loadStorage,
    openFolderPicker,
    navigateToFolder,
    navigateFolderUp,
    selectCurrentFolder,
    loadSources,
    testSourceLookup,
    handleAddSource,
    toggleSource,
    deleteSource,
    openDiscoverSourcesModal,
    loadDiscoverDialogs,
    filterDiscoveredSources,
    toggleAllDiscovered,
    onDiscoveredCheckboxChange,
    saveBatchDiscoveredSources,
    loadJellyfin,
    saveJellyfinConfig,
    testJellyfin,
    triggerJellyfinRefresh,
    loadLogs,
    downloadLogFile,
    clearLogConsole,
    loadSettings,
    saveGeneralSettings,
    loadSystem,
  };
})();
