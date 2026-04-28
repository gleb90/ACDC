import asyncio
import os
import smtplib
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.message import EmailMessage
from time import monotonic

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()


class LeadPayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=6, max_length=30)
    comment: str = Field(default="", max_length=1500)
    company: str = Field(default="", max_length=120)
    object_type: str = Field(default="Не указан", max_length=80)
    page_url: str = Field(default="", max_length=300)
    page_title: str = Field(default="", max_length=180)
    utm_source: str = Field(default="", max_length=120)
    utm_medium: str = Field(default="", max_length=120)
    utm_campaign: str = Field(default="", max_length=120)
    utm_term: str = Field(default="", max_length=120)
    utm_content: str = Field(default="", max_length=160)
    gclid: str = Field(default="", max_length=180)
    yclid: str = Field(default="", max_length=180)
    fbclid: str = Field(default="", max_length=180)


app = FastAPI(title="JYP JYLY Leads API", version="1.0.0")
rate_limit_store: dict[str, deque[float]] = defaultdict(deque)
rate_limit_lock = asyncio.Lock()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGIN", "*").strip()
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _enforce_rate_limit(client_ip: str) -> None:
    max_requests = _env_int("LEAD_RATE_LIMIT_MAX_REQUESTS", 8)
    window_seconds = _env_int("LEAD_RATE_LIMIT_WINDOW_SECONDS", 60)
    if max_requests <= 0:
        return

    now = monotonic()
    async with rate_limit_lock:
        hits = rate_limit_store[client_ip]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()

        if len(hits) >= max_requests:
            raise HTTPException(status_code=429, detail="Слишком много запросов. Повторите через минуту.")

        hits.append(now)


def _is_spam_payload(payload: LeadPayload) -> bool:
    return bool(payload.company.strip())


def _build_notification_text(payload: LeadPayload) -> str:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "Новая заявка с сайта JYP JYLY",
        "",
        f"Имя: {payload.name}",
        f"Телефон: {payload.phone}",
        f"Контекст формы: {payload.object_type}",
    ]

    if payload.comment:
        lines.append(f"Комментарий: {payload.comment}")
    if payload.page_title:
        lines.append(f"Страница: {payload.page_title}")
    if payload.page_url:
        lines.append(f"URL: {payload.page_url}")

    utm_parts = []
    if payload.utm_source:
        utm_parts.append(f"utm_source={payload.utm_source}")
    if payload.utm_medium:
        utm_parts.append(f"utm_medium={payload.utm_medium}")
    if payload.utm_campaign:
        utm_parts.append(f"utm_campaign={payload.utm_campaign}")
    if payload.utm_term:
        utm_parts.append(f"utm_term={payload.utm_term}")
    if payload.utm_content:
        utm_parts.append(f"utm_content={payload.utm_content}")
    if payload.gclid:
        utm_parts.append(f"gclid={payload.gclid}")
    if payload.yclid:
        utm_parts.append(f"yclid={payload.yclid}")
    if payload.fbclid:
        utm_parts.append(f"fbclid={payload.fbclid}")

    if utm_parts:
        lines.append("Рекламные метки:")
        lines.extend(utm_parts)

    lines.append(f"Время: {created_at}")

    return "\n".join(lines)


def _send_email_sync(payload: LeadPayload) -> None:
    smtp_host = _required_env("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = _required_env("SMTP_USERNAME")
    smtp_password = _required_env("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_username)
    smtp_to = _required_env("SMTP_TO")

    message = EmailMessage()
    message["Subject"] = "Новая заявка: JYP JYLY"
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(_build_notification_text(payload))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)


async def send_email(payload: LeadPayload) -> None:
    await asyncio.to_thread(_send_email_sync, payload)


async def send_telegram(payload: LeadPayload) -> None:
    bot_token = _required_env("TELEGRAM_BOT_TOKEN")
    chat_id = _required_env("TELEGRAM_CHAT_ID")
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            api_url,
            json={
                "chat_id": chat_id,
                "text": _build_notification_text(payload),
            },
        )

    if response.status_code >= 400:
        raise RuntimeError(f"Telegram API error: {response.status_code} {response.text}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/leads")
async def create_lead(payload: LeadPayload, request: Request) -> dict[str, str]:
    await _enforce_rate_limit(_get_client_ip(request))

    if _is_spam_payload(payload):
        return {"status": "ok", "message": "Lead accepted"}

    tasks = [
        send_email(payload),
        send_telegram(payload),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [str(result) for result in results if isinstance(result, Exception)]
    if errors:
        raise HTTPException(status_code=502, detail="; ".join(errors))

    return {"status": "ok", "message": "Lead delivered to email and Telegram"}
