const STORAGE_THEME_KEY = "jyp_jyly_theme";
const STORAGE_UTM_KEY = "jyp_jyly_utm";

const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
  "gclid",
  "yclid",
  "fbclid",
];

function getRootSetting(attributeName) {
  const value = document.documentElement.getAttribute(attributeName);
  return value ? value.trim() : "";
}

function injectScript(src, attributes = {}) {
  if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;

    Object.entries(attributes).forEach(([key, value]) => {
      if (value !== undefined && value !== null) script.setAttribute(key, value);
    });

    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Script load failed: ${src}`));
    document.head.appendChild(script);
  });
}

function normalizePath(pathname) {
  let normalized = pathname.toLowerCase();
  normalized = normalized.replace(/index\.html$/, "");
  if (!normalized.endsWith("/")) {
    const lastSlash = normalized.lastIndexOf("/");
    const tail = normalized.slice(lastSlash + 1);
    if (!tail.includes(".")) normalized = `${normalized}/`;
  }
  return normalized;
}

function applyTheme(theme) {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  localStorage.setItem(STORAGE_THEME_KEY, theme);
  const pressed = theme === "light";

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.setAttribute("aria-pressed", String(pressed));
    button.textContent = pressed ? "Тёмная тема" : "Светлая тема";
  });
}

function initTheme() {
  const savedTheme = localStorage.getItem(STORAGE_THEME_KEY);
  const preferredDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(savedTheme || (preferredDark ? "dark" : "light"));

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      applyTheme(current === "dark" ? "light" : "dark");
    });
  });
}

function initStickyHeader() {
  const header = document.querySelector("[data-site-header]");
  if (!header) return;

  const onScroll = () => {
    header.classList.toggle("is-scrolled", window.scrollY > 10);
  };

  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

function initMobileMenu() {
  const menuButton = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector("[data-site-nav]");
  if (!menuButton || !nav) return;

  menuButton.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("is-open");
    menuButton.setAttribute("aria-expanded", String(isOpen));
  });

  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
    });
  });
}

function initActiveMenuLink() {
  const current = normalizePath(window.location.pathname);
  const currentHash = window.location.hash;
  const links = Array.from(document.querySelectorAll("[data-site-nav] a"));

  links.forEach((link) => {
    link.classList.remove("active");
    link.removeAttribute("aria-current");
  });

  let activated = false;
  links.forEach((link) => {
    const url = new URL(link.href, window.location.origin);
    const samePath = normalizePath(url.pathname) === current;
    const hasHash = Boolean(url.hash);
    const hashMatches = currentHash ? url.hash === currentHash : url.hash === "#hero";

    if (samePath && (!hasHash || hashMatches) && !activated) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
      activated = true;
    }
  });
}

function initRevealAnimations() {
  const items = document.querySelectorAll("[data-reveal]");
  if (!items.length) return;

  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion || !("IntersectionObserver" in window)) {
    items.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2, rootMargin: "0px 0px -20px 0px" }
  );

  items.forEach((item) => {
    item.classList.add("reveal");
    observer.observe(item);
  });
}

function readStoredUtm() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_UTM_KEY) || "{}");
  } catch {
    return {};
  }
}

function persistUtmData(data) {
  const payload = {
    ...readStoredUtm(),
    ...data,
    page_path: window.location.pathname,
    captured_at: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_UTM_KEY, JSON.stringify(payload));
}

function captureUtmFromQuery() {
  const query = new URLSearchParams(window.location.search);
  const captured = {};

  UTM_KEYS.forEach((key) => {
    const value = query.get(key);
    if (value) captured[key] = value;
  });

  if (Object.keys(captured).length > 0) persistUtmData(captured);
}

function hydrateUtmInputs() {
  const stored = readStoredUtm();
  document.querySelectorAll("input[data-utm-field]").forEach((input) => {
    const key = input.getAttribute("name");
    input.value = stored[key] || "";
  });
}

function setCurrentYear() {
  const year = String(new Date().getFullYear());
  document.querySelectorAll("[data-current-year]").forEach((node) => {
    node.textContent = year;
  });
}

function initLeadTrackingStubs() {
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };

  const googleAdsSendTo = getRootSetting("data-google-ads-send-to");

  window.trackLeadSubmit = function trackLeadSubmit(payload = {}) {
    window.gtag("event", "generate_lead", {
      event_category: "lead_form",
      event_label: window.location.pathname,
      value: 1,
      ...payload,
    });

    if (googleAdsSendTo) {
      window.gtag("event", "conversion", { send_to: googleAdsSendTo });
    }

    if (window.ym) {
      try {
        window.ym(window.YM_COUNTER_ID, "reachGoal", "lead_submit");
      } catch {
        // Keep no-op if Yandex Metrika is unavailable.
      }
    }
  };
}

async function initGoogleAnalytics() {
  const ga4Id = getRootSetting("data-ga4-id");
  if (!ga4Id) return;

  try {
    await injectScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(ga4Id)}`);
    window.gtag("js", new Date());
    window.gtag("config", ga4Id, {
      anonymize_ip: true,
      transport_type: "beacon",
    });
  } catch {
    // Keep no-op if analytics script fails to load.
  }
}

async function initYandexMetrika() {
  const ymId = getRootSetting("data-ym-id");
  if (!ymId) return;

  window.YM_COUNTER_ID = Number(ymId);
  if (!window.YM_COUNTER_ID) return;

  try {
    await injectScript("https://mc.yandex.ru/metrika/tag.js");
    if (typeof window.ym === "function") {
      window.ym(window.YM_COUNTER_ID, "init", {
        clickmap: true,
        trackLinks: true,
        accurateTrackBounce: true,
        webvisor: false,
      });
    }
  } catch {
    // Keep no-op if metrika script fails to load.
  }
}

function initSite() {
  initTheme();
  initStickyHeader();
  initMobileMenu();
  initActiveMenuLink();
  window.addEventListener("hashchange", initActiveMenuLink);
  initRevealAnimations();
  captureUtmFromQuery();
  hydrateUtmInputs();
  setCurrentYear();
  initLeadTrackingStubs();
  void initGoogleAnalytics();
  void initYandexMetrika();
}

document.addEventListener("DOMContentLoaded", initSite);
