const DEFAULT_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl() {
  const configured = document.documentElement.getAttribute("data-api-base-url");
  if (configured) return configured.trim();
  return DEFAULT_API_BASE_URL;
}

function setStatus(form, message, type) {
  const status = form.querySelector("[data-form-status]");
  if (!status) return;

  status.textContent = message;
  status.classList.remove("is-ok", "is-error");
  if (type) status.classList.add(type === "ok" ? "is-ok" : "is-error");
}

function validatePhone(phone) {
  const normalized = normalizePhoneValue(phone);
  return /^\+7\d{10}$/.test(normalized);
}

function sanitizePhoneValue(value) {
  const hasLeadingPlus = value.trim().startsWith("+");
  const digits = value.replace(/\D/g, "").slice(0, 11);
  return `${hasLeadingPlus ? "+" : ""}${digits}`;
}

function normalizePhoneValue(value) {
  let digits = value.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("8")) {
    digits = `7${digits.slice(1)}`;
  }
  if (digits.length === 10) {
    digits = `7${digits}`;
  }
  return digits ? `+${digits.slice(0, 11)}` : "";
}

function initPhoneInputs() {
  document.querySelectorAll("[data-phone-input]").forEach((input) => {
    input.addEventListener("beforeinput", (event) => {
      if (event.inputType && event.inputType.startsWith("delete")) return;
      if (!event.data) return;
      if (!/^\d$/.test(event.data) && !(event.data === "+" && input.selectionStart === 0 && !input.value.includes("+"))) {
        event.preventDefault();
      }
    });

    input.addEventListener("input", () => {
      const sanitized = sanitizePhoneValue(input.value);
      if (input.value !== sanitized) input.value = sanitized;
    });

    input.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = event.clipboardData ? event.clipboardData.getData("text") : "";
      input.value = sanitizePhoneValue(`${input.value}${text}`);
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });
}

function ensureHoneypotField(form) {
  if (form.querySelector("input[name='company']")) return;

  const wrapper = document.createElement("div");
  wrapper.className = "hp-field";
  wrapper.setAttribute("aria-hidden", "true");

  const input = document.createElement("input");
  input.type = "text";
  input.name = "company";
  input.tabIndex = -1;
  input.autocomplete = "off";
  input.placeholder = "Leave this field blank";

  wrapper.appendChild(input);
  form.appendChild(wrapper);
}

function gatherFormPayload(form) {
  const formData = new FormData(form);
  return {
    name: String(formData.get("name") || "").trim(),
    phone: normalizePhoneValue(String(formData.get("phone") || "").trim()),
    comment: String(formData.get("comment") || "").trim(),
    company: String(formData.get("company") || "").trim(),
    object_type: String(formData.get("object_type") || "").trim(),
    page_url: window.location.href,
    page_title: document.title,
    utm_source: String(formData.get("utm_source") || "").trim(),
    utm_medium: String(formData.get("utm_medium") || "").trim(),
    utm_campaign: String(formData.get("utm_campaign") || "").trim(),
    utm_term: String(formData.get("utm_term") || "").trim(),
    utm_content: String(formData.get("utm_content") || "").trim(),
    gclid: String(formData.get("gclid") || "").trim(),
    yclid: String(formData.get("yclid") || "").trim(),
    fbclid: String(formData.get("fbclid") || "").trim(),
  };
}

async function submitLead(form) {
  const submitButton = form.querySelector("button[type='submit']");
  const originalLabel = submitButton ? submitButton.textContent : "Отправить";
  const payload = gatherFormPayload(form);

  if (!payload.name) {
    setStatus(form, "Укажите имя для связи.", "error");
    return;
  }

  if (!validatePhone(payload.phone)) {
    setStatus(form, "Введите корректный телефон.", "error");
    return;
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 12000);

  setStatus(form, "Отправляем заявку...", "");
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Отправка...";
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Сервис временно недоступен.");
    }

    setStatus(form, "Заявка принята. Инженер свяжется с вами в ближайшее время.", "ok");
    form.reset();
    if (window.trackLeadSubmit) window.trackLeadSubmit({ form_id: form.id || "lead_form" });
  } catch (error) {
    const message =
      error instanceof DOMException && error.name === "AbortError"
        ? "Сервис долго не отвечает. Позвоните нам или повторите отправку позже."
        : error instanceof Error
          ? error.message
          : "Ошибка отправки. Повторите попытку.";
    setStatus(form, message, "error");
  } finally {
    window.clearTimeout(timeoutId);
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalLabel;
    }
  }
}

function initLeadForms() {
  const forms = document.querySelectorAll("[data-lead-form]");
  if (!forms.length) return;

  forms.forEach((form) => {
    ensureHoneypotField(form);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitLead(form);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initPhoneInputs();
  initLeadForms();
});
