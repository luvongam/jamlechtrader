"""Notification system for trade alerts."""

from __future__ import annotations

import json
import smtplib
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from typing import Any

import requests
from loguru import logger


class Notifier(ABC):
    """Base notifier interface."""

    @abstractmethod
    def send(self, message: str, **kwargs) -> bool:
        """Send notification."""
        pass


class EmailNotifier(Notifier):
    """Send email notifications via SMTP."""

    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, from_addr: str, to_addrs: list[str]) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send(self, message: str, subject: str = "Trading Alert") -> bool:
        try:
            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            logger.info("Email notification sent")
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False


class WebhookNotifier(Notifier):
    """Send notifications via webhook (Slack, Discord, etc.)."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, message: str, **kwargs) -> bool:
        try:
            payload = {"text": message, **kwargs}
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Webhook notification sent")
            return True
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False


class NotificationManager:
    """Manage multiple notifiers."""

    def __init__(self) -> None:
        self.notifiers: list[Notifier] = []

    def add_notifier(self, notifier: Notifier) -> None:
        self.notifiers.append(notifier)

    def notify_trade(self, symbol: str, side: str, price: float, quantity: float) -> None:
        message = f"🔔 Trade Alert\nSymbol: {symbol}\nSide: {side}\nPrice: {price}\nQuantity: {quantity}"
        for notifier in self.notifiers:
            notifier.send(message)

    def notify_error(self, error: str) -> None:
        message = f"⚠️ Error: {error}"
        for notifier in self.notifiers:
            notifier.send(message, subject="Trading Bot Error")
