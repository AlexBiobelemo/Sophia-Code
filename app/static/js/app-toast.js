(() => {
  function ensureToastContainer() {
    let container = document.querySelector(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container position-fixed top-0 end-0 p-3";
      document.body.appendChild(container);
    }
    return container;
  }

  function variantMeta(variant) {
    const v = (variant || "info").toLowerCase();
    const map = {
      success: { bg: "bg-success", icon: "bi-check-circle-fill", label: "Success" },
      danger: { bg: "bg-danger", icon: "bi-exclamation-triangle-fill", label: "Error" },
      warning: { bg: "bg-warning text-dark", icon: "bi-exclamation-circle-fill", label: "Warning" },
      info: { bg: "bg-info text-dark", icon: "bi-info-circle-fill", label: "Info" },
    };
    return map[v] || map.info;
  }

  window.appToast = (message, variant = "info", options = {}) => {
    const container = ensureToastContainer();
    const { bg, icon, label } = variantMeta(variant);

    const delay = Number.isFinite(options.delay) ? options.delay : 5000;
    const title = options.title || label;
    const safeMessage = String(message ?? "");

    const toastEl = document.createElement("div");
    toastEl.className = `toast app-toast align-items-center ${bg} border-0`;
    toastEl.role = "alert";
    toastEl.ariaLive = "assertive";
    toastEl.ariaAtomic = "true";

    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <div class="app-toast-title">
            <i class="bi ${icon} me-2" aria-hidden="true"></i>
            <span>${title}</span>
          </div>
          <div class="app-toast-message">${safeMessage}</div>
        </div>
        <button type="button" class="btn-close ${bg.includes("text-dark") ? "" : "btn-close-white"} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    container.appendChild(toastEl);

    // Bootstrap toast if available; otherwise show/hide manually
    if (window.bootstrap?.Toast) {
      const instance = new bootstrap.Toast(toastEl, { delay });
      instance.show();
      toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
    } else {
      toastEl.classList.add("show");
      setTimeout(() => toastEl.remove(), delay);
    }
  };

  window.appAlert = (message, variant = "info", options = {}) => {
    window.appToast(message, variant, options);
  };

  window.consumeFlashMessages = () => {
    const flashRoot = document.getElementById("flash-messages");
    if (!flashRoot) return;
    flashRoot.querySelectorAll(".flash").forEach((el) => {
      const message = el.getAttribute("data-message") || "";
      const category = el.getAttribute("data-category") || "info";
      window.appToast(message, category);
    });
    flashRoot.remove();
  };

  document.addEventListener("DOMContentLoaded", () => {
    try {
      window.consumeFlashMessages();
    } catch (_) {}
  });

  // Replace blocking browser alerts with app toasts in non-debug mode.
  // This avoids native popups and keeps notifications visually consistent.
  try {
    const isDebug = Boolean(window.APP_DEBUG);
    if (!isDebug && typeof window.alert === "function") {
      window.alert = (msg) => window.appToast(String(msg ?? ""), "info", { title: "Notice" });
    }
  } catch (_) {}
})();
