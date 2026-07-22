/* ==========================================================================
   منصة مساعد — Core front-end (app.js)
   Theme switcher · Toasts · Form helpers · Service worker.
   No build step; vanilla ES, loaded with `defer`.
   ========================================================================== */
(function () {
  "use strict";

  /* ----- 1. THEME (dark mode) ----------------------------------------- */
  var THEME_KEY = "ms-theme";
  var root = document.documentElement;

  function applyTheme(theme) {
    root.setAttribute("data-bs-theme", theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
    document.querySelectorAll("[data-theme-label]").forEach(function (el) {
      el.textContent = theme === "dark" ? "الوضع الفاتح" : "الوضع الداكن";
    });
  }

  function initTheme() {
    var saved;
    try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
    if (!saved) {
      saved = window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    applyTheme(saved);
  }

  function toggleTheme() {
    var current = root.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
    applyTheme(current === "dark" ? "light" : "dark");
  }

  // Apply ASAP to avoid a flash of the wrong theme.
  initTheme();

  /* ----- 2. TOASTS ---------------------------------------------------- */
  function ensureToastStack() {
    var stack = document.querySelector(".ms-toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "ms-toast-stack";
      stack.setAttribute("aria-live", "polite");
      stack.setAttribute("aria-atomic", "true");
      document.body.appendChild(stack);
    }
    return stack;
  }

  var TOAST_ICONS = {
    success: "bi-check-circle-fill",
    warning: "bi-exclamation-triangle-fill",
    danger:  "bi-x-circle-fill",
    info:    "bi-info-circle-fill"
  };

  function toast(message, type, timeout) {
    type = type || "info";
    var stack = ensureToastStack();
    var el = document.createElement("div");
    el.className = "ms-toast ms-toast--" + type;
    el.setAttribute("role", "status");
    el.innerHTML =
      '<i class="bi ' + (TOAST_ICONS[type] || TOAST_ICONS.info) + '"></i>' +
      '<div class="flex-grow-1 small fw-semibold"></div>' +
      '<button type="button" class="btn-close ms-2" aria-label="إغلاق"></button>';
    el.querySelector("div").textContent = message;
    stack.appendChild(el);

    function dismiss() {
      el.classList.add("hide");
      setTimeout(function () { el.remove(); }, 300);
    }
    el.querySelector(".btn-close").addEventListener("click", dismiss);
    setTimeout(dismiss, timeout || 4500);
    return el;
  }

  /* ----- 3. FLASH MESSAGES -> TOASTS ---------------------------------- */
  // Server injects flashes into <script type="application/json" id="ms-flashes">.
  function initFlashes() {
    var node = document.getElementById("ms-flashes");
    if (!node) return;
    var items = [];
    try { items = JSON.parse(node.textContent || "[]"); } catch (e) {}
    items.forEach(function (raw) {
      var msg = String(raw);
      var type = "info";
      if (/✅|نجاح|بنجاح|تم /.test(msg)) type = "success";
      else if (/⚠️|تنبيه|مشاب/.test(msg)) type = "warning";
      else if (/❌|خطأ|فشل/.test(msg)) type = "danger";
      toast(msg.replace(/^[✅⚠️❌🔔\s]+/, ""), type, 6000);
    });
  }

  /* ----- 4. PASSWORD SHOW/HIDE ---------------------------------------- */
  function initPasswordToggles() {
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sel = btn.getAttribute("data-toggle-password");
        var input = document.querySelector(sel);
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        var icon = btn.querySelector("i");
        if (icon) icon.className = show ? "bi bi-eye-slash" : "bi bi-eye";
      });
    });
  }

  /* ----- 5. WIRE UP THEME TOGGLE BUTTONS ------------------------------ */
  function initToggleButtons() {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", toggleTheme);
    });
  }

  /* ----- 6. BOOKMARKS (localStorage) ---------------------------------- */
  var BOOKMARK_KEY = "ms-bookmarks";

  function getBookmarks() {
    try { return JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveBookmarks(list) {
    try { localStorage.setItem(BOOKMARK_KEY, JSON.stringify(list)); } catch (e) {}
  }
  function isBookmarked(id) {
    return getBookmarks().some(function (b) { return String(b.id) === String(id); });
  }
  function toggleBookmark(item) {
    var list = getBookmarks();
    var idx = list.findIndex(function (b) { return String(b.id) === String(item.id); });
    var added;
    if (idx === -1) { list.push(item); added = true; }
    else { list.splice(idx, 1); added = false; }
    saveBookmarks(list);
    return added;
  }

  function paintBookmarkButton(btn) {
    var on = isBookmarked(btn.getAttribute("data-bookmark-id"));
    var icon = btn.querySelector("i");
    if (icon) icon.className = on ? "bi bi-bookmark-fill" : "bi bi-bookmark";
    btn.classList.toggle("text-brand", on);
    btn.setAttribute("title", on ? "إزالة من المحفوظات" : "حفظ");
  }

  function initBookmarks() {
    var btns = document.querySelectorAll(".ms-bookmark-btn");
    btns.forEach(paintBookmarkButton);
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".ms-bookmark-btn");
      if (!btn) return;
      var added = toggleBookmark({
        id: btn.getAttribute("data-bookmark-id"),
        title: btn.getAttribute("data-bookmark-title"),
        subject: btn.getAttribute("data-bookmark-subject"),
        file: btn.getAttribute("data-bookmark-file")
      });
      paintBookmarkButton(btn);
      toast(added ? "تمت الإضافة إلى المحفوظات" : "تمت الإزالة من المحفوظات",
        added ? "success" : "info", 2500);
    });
  }

  /* ----- 7. SHARE ----------------------------------------------------- */
  function initShare() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".ms-share-btn");
      if (!btn) return;
      var url = btn.getAttribute("data-share-url");
      var title = btn.getAttribute("data-share-title") || document.title;
      if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          toast("تم نسخ الرابط", "success", 2500);
        }).catch(function () { toast("تعذّر النسخ", "danger", 2500); });
      } else {
        toast(url, "info", 5000);
      }
    });
  }

  /* ----- 8. SERVICE WORKER -------------------------------------------- */
  function initServiceWorker() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/service-worker.js").catch(function () {});
    }
  }

  /* ----- 9. BOOT ------------------------------------------------------ */
  document.addEventListener("DOMContentLoaded", function () {
    initToggleButtons();
    initPasswordToggles();
    initFlashes();
    initBookmarks();
    initShare();
    initServiceWorker();
  });

  // Public API
  window.MS = {
    toast: toast, toggleTheme: toggleTheme, setTheme: applyTheme,
    getBookmarks: getBookmarks
  };
})();
