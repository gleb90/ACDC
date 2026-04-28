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
  return /^[+()\-0-9\s]{6,24}$/.test(phone);
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
    phone: String(formData.get("phone") || "").trim(),
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
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Сервис временно недоступен.");
    }

    setStatus(form, "Заявка принята. Инженер свяжется с вами в ближайшее время.", "ok");
    form.reset();
    if (window.trackLeadSubmit) window.trackLeadSubmit({ form_id: form.id || "lead_form" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Ошибка отправки. Повторите попытку.";
    setStatus(form, message, "error");
  } finally {
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

document.addEventListener("DOMContentLoaded", initLeadForms);
