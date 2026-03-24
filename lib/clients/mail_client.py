"""lib/mail_client.py - SMTP email notification client."""

import configparser
from lib.config_loader import load_config
import logging
import smtplib
from lib.exceptions import ConfigError
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.ini"


def _load_mail_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.critical("settings.ini not found: %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    config = load_config(CONFIG_PATH)
    if "mail" not in config:
        logger.critical("Missing [mail] section in %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    m = config["mail"]
    return {
        "host":     m["host"],
        "port":     int(m.get("port", "25")),
        "from":     m["from"],
        "to":       [addr.strip() for addr in m["to"].split(",")],
        "user":     m.get("user", ""),
        "password": m.get("password", ""),
        "use_tls":  config.getboolean("mail", "use_tls", fallback=False),
    }


def send_error_mail(subject: str, body: str) -> None:
    """Send an error notification email."""
    try:
        conf = _load_mail_config()
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"]    = conf["from"]
        msg["To"]      = ", ".join(conf["to"])

        if conf["use_tls"]:
            smtp = smtplib.SMTP_SSL(conf["host"], conf["port"])
        else:
            smtp = smtplib.SMTP(conf["host"], conf["port"])

        if conf["user"] and conf["password"]:
            smtp.login(conf["user"], conf["password"])

        smtp.sendmail(conf["from"], conf["to"], msg.as_string())
        smtp.quit()
        logger.info("Error mail sent: %s", subject)
    except Exception:
        logger.exception("Failed to send error mail.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    send_error_mail(
        subject="[TEST] mail_client test",
        body="This is a test email from mail_client.py.",
    )
    print("Done.")
