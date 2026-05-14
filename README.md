# JYP JYLY Website

Одностраничный B2B лендинг компании по комплексной эксплуатации зданий в Алматы.

## Структура

```text
/
  index.html
  assets/
    css/styles.css
    js/site.js
    js/forms.js
  robots.txt
  sitemap.xml
  backend/
    main.py
    requirements.txt
    .env.example
```

## Запуск фронтенда

### Вариант 1: через Vite (рекомендуется для разработки)

```powershell
cd C:\Users\gsham\OneDrive\Desktop\ACDC
npm install
npm run dev
```

Открыть: `http://localhost:5173`

### Вариант 2: как статический сайт

Можно разместить файлы на любом статическом хостинге (Nginx, Netlify, Vercel, Cloudflare Pages).

## Запуск backend (FastAPI)

```powershell
cd C:\Users\gsham\OneDrive\Desktop\ACDC\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Заполните `.env`, затем:

```powershell
.\.venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Проверка: `http://localhost:8000/health`

## Что уже включено

- Полная адаптивность (mobile/tablet/desktop).
- Sticky header, якорная навигация, плавный скролл, light/dark тема, scroll reveal.
- SEO-основа: title/description/keywords/h1-h3/canonical/og.
- Две формы на одном лендинге: выше фолда и в финальном блоке.
- Фиксированная кнопка `Оставить заявку`.
- Отправка заявок одновременно в Telegram и Email.
- Сбор UTM-меток (`utm_*`, `gclid`, `yclid`, `fbclid`) и передача в backend.
- Антиспам: honeypot-поле + rate limit по IP на backend.
- `robots.txt` и `sitemap.xml`.

## Подключение аналитики и рекламы

В `index.html` на теге `<html>` есть атрибуты:

```html
data-ga4-id=""
data-ym-id=""
data-google-ads-send-to=""
```

- `data-ga4-id`: ID GA4, например `G-XXXXXXXXXX`.
- `data-ym-id`: ID счетчика Яндекс Метрики, например `12345678`.
- `data-google-ads-send-to`: conversion destination, например `AW-123456789/AbCdEfGhIjkLmNoP`.

После заполнения ID фронтенд сам подключит нужные скрипты и отправку событий `generate_lead`.

## Перед публикацией

1. Обновить домен в `canonical`, `sitemap.xml`, `robots.txt`.
2. Указать реальные контакты на лендинге.
3. Заполнить IDs аналитики в атрибутах `<html>`.
4. Проверить `.env` backend (SMTP, Telegram, CORS, лимиты антиспама).
