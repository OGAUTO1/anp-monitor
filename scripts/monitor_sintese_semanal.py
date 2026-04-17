import hashlib
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia"
    "/precos/sintese-semanal-do-comportamento-dos-precos-dos-combustiveis"
)
STATE_FILE = "state/sintese_semanal_anp.json"
BASE_NAME = "Síntese Semanal de Preços - ANP"
EXTENSIONS = {".pdf", ".xlsx", ".zip", ".csv", ".ods"}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")


def load_state(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path: str, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 403:
        print("[INFO] Got 403, falling back to Playwright...")
        return _fetch_with_playwright(url)
    resp.raise_for_status()
    return resp.text


def _fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        content = page.content()
        browser.close()
    return content


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    seen = set()
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        full = urljoin(base_url, href)
        ext = os.path.splitext(urlparse(full).path)[1].lower()
        if ext in EXTENSIONS and full not in seen:
            seen.add(full)
            links.append(full)
    return links


def compute_hash(urls: set[str]) -> str:
    serialized = json.dumps(sorted(urls), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


def build_alert_html(base_name: str, new_links: list[str], page_url: str) -> str:
    brt = datetime.now(timezone(timedelta(hours=-3)))
    timestamp = brt.strftime("%Y-%m-%d %H:%M BRT")
    items = "".join(
        f'• <a href="{link}">{os.path.basename(urlparse(link).path) or link}</a>\n'
        for link in new_links
    )
    return (
        f"🚨 <b>Novo arquivo detectado!</b>\n\n"
        f"📊 <b>Base:</b> {base_name}\n"
        f"🕒 <b>Detectado em:</b> {timestamp}\n\n"
        f"<b>Novos arquivos:</b>\n{items}\n"
        f'🔗 <a href="{page_url}">Acessar página da ANP</a>'
    )


def send_telegram(token: str, chat_id: str, html_message: str) -> None:
    if not token or not chat_id:
        print("[WARN] Telegram credentials not configured, skipping alert.")
        return
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(api_url, json=payload, timeout=30)
    resp.raise_for_status()
    print("[INFO] Telegram alert sent.")


def send_email(
    smtp_user: str,
    smtp_pass: str,
    smtp_server: str,
    smtp_port: int,
    to: str,
    subject: str,
    html_body: str,
) -> None:
    if not smtp_user or not smtp_pass or not to:
        print("[WARN] Email credentials not configured, skipping alert.")
        return
    recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_string())
    print(f"[INFO] Email alert sent to {len(recipients)} recipient(s).")


def main() -> None:
    print(f"[INFO] Checking: {URL}")
    state = load_state(STATE_FILE)
    is_first_run = not state.get("urls")

    html = fetch_page(URL)
    current_urls = set(extract_links(html, URL))
    print(f"[INFO] Found {len(current_urls)} file link(s) on page.")

    known_urls = set(state.get("urls", []))
    new_links = sorted(current_urls - known_urls)
    now = datetime.now(timezone.utc).isoformat()

    if is_first_run:
        print(f"[INFO] First run — seeding state with {len(current_urls)} URL(s), no alerts sent.")
    elif new_links:
        print(f"[INFO] {len(new_links)} new link(s) detected.")
        alert_html = build_alert_html(BASE_NAME, new_links, URL)
        send_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, alert_html)
        subject = f"[ANP Monitor] {len(new_links)} novo(s) arquivo(s) — {BASE_NAME}"
        send_email(SMTP_USER, SMTP_PASSWORD, SMTP_SERVER, SMTP_PORT, ALERT_EMAIL_TO, subject, alert_html)
    else:
        print("[INFO] No new links detected.")

    state.update({
        "hash": compute_hash(current_urls),
        "urls": sorted(current_urls),
        "last_checked": now,
        "last_updated": now if (new_links and not is_first_run) else state.get("last_updated", now),
        "new_links": new_links if not is_first_run else [],
    })
    save_state(STATE_FILE, state)
    print("[INFO] State saved.")


if __name__ == "__main__":
    main()
