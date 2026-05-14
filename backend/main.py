import asyncio
import os
import sqlite3
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator


load_dotenv(Path(__file__).with_name(".env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_CHAT_IDS = [chat_id.strip() for chat_id in TELEGRAM_CHAT_ID.split(",") if chat_id.strip()]
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587").strip() or "587")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USERNAME).strip()
MAIL_TO = os.getenv("MAIL_TO", "g.shamanayevz@gmail.com").strip()
DB_PATH = Path(__file__).with_name("leads.sqlite3")
LOCAL_TZ = timezone(timedelta(hours=5))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app = FastAPI(title="JYP JYLY Leads API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

rate_limit: dict[str, list[float]] = {}
telegram_polling_task: asyncio.Task | None = None


class LeadPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=6, max_length=24)
    comment: str = Field(default="", max_length=1200)
    company: str = Field(default="", max_length=200)
    object_type: str = Field(default="", max_length=120)
    page_url: str = Field(default="", max_length=500)
    page_title: str = Field(default="", max_length=250)
    utm_source: str = Field(default="", max_length=200)
    utm_medium: str = Field(default="", max_length=200)
    utm_campaign: str = Field(default="", max_length=200)
    utm_term: str = Field(default="", max_length=200)
    utm_content: str = Field(default="", max_length=200)
    gclid: str = Field(default="", max_length=300)
    yclid: str = Field(default="", max_length=300)
    fbclid: str = Field(default="", max_length=300)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = "".join(char for char in value if char.isdigit())
        if len(digits) == 11 and digits.startswith("8"):
            digits = f"7{digits[1:]}"
        if len(digits) == 10:
            digits = f"7{digits}"
        normalized = f"+{digits[:11]}" if digits else ""
        if not normalized or len(digits) != 11 or not normalized.startswith("+7"):
            raise ValueError("Введите корректный телефон в формате +7XXXXXXXXXX.")
        return normalized


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db_connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                object_type TEXT NOT NULL DEFAULT '',
                page_url TEXT NOT NULL DEFAULT '',
                ip TEXT NOT NULL DEFAULT ''
            )
            """
        )


def save_lead(payload: LeadPayload, ip: str) -> None:
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO leads (created_at, name, phone, comment, object_type, page_url, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                payload.name,
                payload.phone,
                payload.comment,
                payload.object_type,
                payload.page_url,
                ip,
            ),
        )


def get_unique_clients() -> list[sqlite3.Row]:
    with db_connect() as connection:
        return connection.execute(
            """
            SELECT name, phone
            FROM leads
            WHERE id IN (
                SELECT MAX(id)
                FROM leads
                GROUP BY phone
            )
            ORDER BY id DESC
            """
        ).fetchall()


def format_clients_message() -> str:
    clients = get_unique_clients()
    if not clients:
        return "Клиентов пока нет."

    lines = [f"Клиентов в базе: {len(clients)}", ""]
    lines.extend(f"{row['name']} - {row['phone']}" for row in clients)
    return "\n".join(lines)


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - 60
    attempts = [stamp for stamp in rate_limit.get(ip, []) if stamp > window_start]
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Слишком много заявок. Попробуйте позже.")
    attempts.append(now)
    rate_limit[ip] = attempts


def format_lead_message(payload: LeadPayload, ip: str) -> str:
    received_at = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y %H:%M")
    lines = [
        "Новая заявка с сайта JYP JYLY",
        "",
        f"Дата и время: {received_at}",
        f"Имя: {payload.name}",
        f"Телефон: {payload.phone}",
    ]

    if payload.comment:
        lines.append(f"Комментарий: {payload.comment}")
    utm: dict[str, Any] = {
        "utm_source": payload.utm_source,
        "utm_medium": payload.utm_medium,
        "utm_campaign": payload.utm_campaign,
        "utm_term": payload.utm_term,
        "utm_content": payload.utm_content,
        "gclid": payload.gclid,
        "yclid": payload.yclid,
        "fbclid": payload.fbclid,
    }
    filled_utm = [f"{key}: {value}" for key, value in utm.items() if value]
    if filled_utm:
        lines.extend(["", "Метки:", *filled_utm])

    return "\n".join(lines)


async def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        raise HTTPException(status_code=500, detail="Telegram не настроен: добавьте BOT_TOKEN и CHAT_ID в backend/.env.")

    for chat_id in TELEGRAM_CHAT_IDS:
        await send_bot_message(chat_id, text)


def email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and MAIL_FROM and MAIL_TO)


def send_email_message(text: str) -> None:
    if not email_configured():
        return

    message = EmailMessage()
    message["Subject"] = "Новая заявка с сайта JYP JYLY"
    message["From"] = MAIL_FROM
    message["To"] = MAIL_TO
    message.set_content(text)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(message)


async def notify_lead(text: str) -> None:
    try:
        await send_telegram_message(text)
    except Exception as error:
        print(f"Telegram delivery failed: {error}")

    try:
        await asyncio.to_thread(send_email_message, text)
    except Exception as error:
        print(f"Email delivery failed: {error}")


async def send_bot_message(chat_id: str | int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(url, json=payload)

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Telegram не принял заявку. Проверьте токен и нажмите Start у бота.")


async def answer_callback_query(callback_id: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    async with httpx.AsyncClient(timeout=8) as client:
        await client.post(url, json={"callback_query_id": callback_id})


async def set_bot_commands() -> None:
    if not TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    async with httpx.AsyncClient(timeout=8) as client:
        await client.post(
            url,
            json={
                "commands": [
                    {"command": "clients", "description": "База клиентов"},
                ],
            },
        )


async def handle_telegram_update(update: dict[str, Any]) -> None:
    message = update.get("message") or {}
    callback = update.get("callback_query") or {}

    if callback:
        callback_id = str(callback.get("id", ""))
        chat = (callback.get("message") or {}).get("chat") or {}
        chat_id = str(chat.get("id", ""))
        data = callback.get("data")
        if callback_id:
            await answer_callback_query(callback_id)
        if chat_id in TELEGRAM_CHAT_IDS and data == "clients:list":
            await send_bot_message(chat_id, format_clients_message())
        return

    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = str(message.get("text", "")).strip().lower()
    if chat_id not in TELEGRAM_CHAT_IDS:
        return

    if text in {"/start", "старт"}:
        await send_bot_message(
            chat_id,
            "Бот подключен к сайту JYP JYLY. Откройте меню команд и выберите /clients.",
        )
    elif text in {"/clients", "база клиентов", "клиенты"}:
        await send_bot_message(chat_id, format_clients_message())


async def poll_telegram_updates() -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        await client.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook")
        while True:
            try:
                response = await client.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                    params={"timeout": 25, "offset": offset, "allowed_updates": '["message","callback_query"]'},
                )
                response.raise_for_status()
                updates = response.json().get("result", [])
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    await handle_telegram_update(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)


@app.on_event("startup")
async def on_startup() -> None:
    global telegram_polling_task
    init_db()
    await set_bot_commands()
    telegram_polling_task = asyncio.create_task(poll_telegram_updates())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if telegram_polling_task:
        telegram_polling_task.cancel()


@app.get("/health")
async def health() -> dict[str, bool]:
    return {
        "ok": True,
        "telegram_chat_id_configured": bool(TELEGRAM_CHAT_IDS),
        "telegram_token_configured": bool(TELEGRAM_BOT_TOKEN),
        "email_configured": email_configured(),
        "database_configured": DB_PATH.exists(),
    }


@app.post("/api/leads")
async def create_lead(payload: LeadPayload, request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
    if payload.company:
        return {"ok": True}

    ip = client_ip(request)
    check_rate_limit(ip)
    save_lead(payload, ip)
    message = format_lead_message(payload, ip)
    background_tasks.add_task(notify_lead, message)
    return {"ok": True}
