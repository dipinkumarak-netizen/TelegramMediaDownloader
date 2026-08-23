/**
 * First-Run Setup Wizard Controller
 */
window.Wizard = (function () {
  let currentStep = 1;
  const totalSteps = 6;

  function init() {
    currentStep = 1;
    updateStepUI();
  }

  function showStep(step) {
    currentStep = step;
    updateStepUI();
  }

  function nextStep() {
    if (currentStep < totalSteps) {
      currentStep++;
      updateStepUI();
    }
  }

  function prevStep() {
    if (currentStep > 1) {
      currentStep--;
      updateStepUI();
    }
  }

  function updateStepUI() {
    // Update active pane
    document.querySelectorAll(".wizard-step-pane").forEach((pane, idx) => {
      pane.classList.toggle("active", idx + 1 === currentStep);
    });

    // Update dots
    document.querySelectorAll(".step-dot").forEach((dot, idx) => {
      dot.classList.toggle("active", idx + 1 === currentStep);
    });

    // Step titles
    const titles = [
      "Welcome to Telegram Downloader",
      "Create Administrator Account",
      "Select Download Storage Location",
      "Configure Telegram API",
      "Configure Optional Jellyfin",
      "Review & Complete Setup"
    ];
    const titleEl = document.getElementById("wizard-step-title");
    if (titleEl) titleEl.innerText = titles[currentStep - 1] || "Setup Wizard";

    if (currentStep === 6) {
      populateReviewSummary();
    }
  }

  function validateStep2() {
    const user = document.getElementById("wiz-username").value.trim();
    const pass = document.getElementById("wiz-password").value;
    const confirm = document.getElementById("wiz-password-confirm").value;

    if (user.length < 3) {
      window.App.toast("Username must be at least 3 characters.", "error");
      return;
    }
    if (pass.length < 6) {
      window.App.toast("Password must be at least 6 characters.", "error");
      return;
    }
    if (pass !== confirm) {
      window.App.toast("Passwords do not match.", "error");
      return;
    }
    nextStep();
  }

  async function validateStep3() {
    const downloadDir = document.getElementById("wiz-download-dir").value.trim();
    if (!downloadDir) {
      window.App.toast("Please enter or select a download directory.", "error");
      return;
    }

    try {
      const res = await window.App.apiCall("/api/storage/validate", "POST", { path: downloadDir });
      if (!res.valid) {
        window.App.toast(res.message, "error");
        return;
      }
      nextStep();
    } catch (e) {
      window.App.toast("Failed to validate directory path: " + e.message, "error");
    }
  }

  function validateStep4() {
    const apiIdStr = document.getElementById("wiz-api-id").value.trim();
    const apiHash = document.getElementById("wiz-api-hash").value.trim();
    const phone = document.getElementById("wiz-phone").value.trim();

    if (apiIdStr || apiHash || phone) {
      const apiId = parseInt(apiIdStr, 10);
      if (isNaN(apiId) || apiId < 1 || apiId > 2147483647) {
        window.App.toast("Invalid Telegram API ID. Must be a 32-bit signed integer (1 to 2147483647). Please check my.telegram.org/apps.", "error");
        return;
      }
      if (!apiHash) {
        window.App.toast("Please enter your Telegram API Hash.", "error");
        return;
      }
      if (!phone) {
        window.App.toast("Please enter your Telegram phone number.", "error");
        return;
      }
    }
    nextStep();
  }

  function populateReviewSummary() {
    const user = document.getElementById("wiz-username").value.trim();
    const downloadDir = document.getElementById("wiz-download-dir").value.trim();
    const apiId = document.getElementById("wiz-api-id").value.trim();
    const phone = document.getElementById("wiz-phone").value.trim();
    const jfUrl = document.getElementById("wiz-jellyfin-url").value.trim();

    const summaryHtml = `
      <div class="status-rows">
        <div class="status-row"><span>Admin Username:</span><strong>${user}</strong></div>
        <div class="status-row"><span>Download Storage:</span><strong class="font-mono">${downloadDir}</strong></div>
        <div class="status-row"><span>Telegram API ID:</span><strong>${apiId || 'Configured later'}</strong></div>
        <div class="status-row"><span>Telegram Phone:</span><strong>${phone || 'Configured later'}</strong></div>
        <div class="status-row"><span>Jellyfin Server:</span><strong>${jfUrl || 'Disabled'}</strong></div>
      </div>
    `;
    document.getElementById("wiz-review-summary").innerHTML = summaryHtml;
  }

  async function submitSetup() {
    const payload = {
      username: document.getElementById("wiz-username").value.trim(),
      password: document.getElementById("wiz-password").value,
      download_dir: document.getElementById("wiz-download-dir").value.trim(),
      telegram_api_id: document.getElementById("wiz-api-id").value.trim() ? parseInt(document.getElementById("wiz-api-id").value.trim(), 10) : null,
      telegram_api_hash: document.getElementById("wiz-api-hash").value.trim() || null,
      telegram_phone: document.getElementById("wiz-phone").value.trim() || null,
      jellyfin_url: document.getElementById("wiz-jellyfin-url").value.trim() || null,
      jellyfin_api_key: document.getElementById("wiz-jellyfin-key").value.trim() || null,
      jellyfin_auto_refresh: document.getElementById("wiz-jellyfin-auto").checked,
    };

    try {
      window.App.showLoading("Initializing server...");
      const res = await window.App.apiCall("/api/auth/setup", "POST", payload);
      window.App.hideLoading();
      window.App.toast("Setup completed successfully!", "success");
      document.getElementById("wizard-modal").classList.add("hidden");
      await window.App.initDashboard();
    } catch (e) {
      window.App.hideLoading();
      window.App.toast(e.message, "error");
    }
  }

  return {
    init,
    showStep,
    nextStep,
    prevStep,
    validateStep2,
    validateStep3,
    validateStep4,
    submitSetup,
  };
})();
