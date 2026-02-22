"""Alert manager with pluggable channels and suppression."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertChannel(ABC):
    """Base alert delivery channel."""

    @abstractmethod
    def send(self, severity: AlertSeverity, message: str, data: dict[str, Any] | None = None) -> bool:
        ...


class SlackAlertChannel(AlertChannel):
    """Send alerts to Slack via webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def send(self, severity: AlertSeverity, message: str, data: dict[str, Any] | None = None) -> bool:
        try:
            import httpx

            emoji = {"INFO": ":information_source:", "WARNING": ":warning:", "CRITICAL": ":rotating_light:"}.get(
                severity.value, ""
            )
            payload = {"text": f"{emoji} [{severity.value}] {message}"}
            resp = httpx.post(self._webhook_url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
            return False


class PagerDutyAlertChannel(AlertChannel):
    """Send alerts to PagerDuty."""

    def __init__(self, routing_key: str) -> None:
        self._routing_key = routing_key

    def send(self, severity: AlertSeverity, message: str, data: dict[str, Any] | None = None) -> bool:
        try:
            import httpx

            pd_severity = {"INFO": "info", "WARNING": "warning", "CRITICAL": "critical"}.get(
                severity.value, "info"
            )
            payload = {
                "routing_key": self._routing_key,
                "event_action": "trigger",
                "payload": {
                    "summary": message,
                    "severity": pd_severity,
                    "source": "jamlechtrader",
                    "custom_details": data or {},
                },
            }
            resp = httpx.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10,
            )
            return resp.status_code == 202
        except Exception as e:
            logger.error(f"PagerDuty alert failed: {e}")
            return False


class WebhookAlertChannel(AlertChannel):
    """Send alerts to a generic webhook."""

    def __init__(self, url: str) -> None:
        self._url = url

    def send(self, severity: AlertSeverity, message: str, data: dict[str, Any] | None = None) -> bool:
        try:
            import httpx

            payload = {"severity": severity.value, "message": message, "data": data or {}}
            resp = httpx.post(self._url, json=payload, timeout=10)
            return resp.is_success
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False


@dataclass
class AlertRule:
    """Alert rule with condition function, severity, and message template."""

    name: str
    condition: Callable[[], bool]
    severity: AlertSeverity
    message_template: str
    data_fn: Callable[[], dict[str, Any]] | None = None


class AlertManager:
    """Manages alert channels, rules, and suppression windows."""

    def __init__(self, suppression_seconds: float = 300.0) -> None:
        self._channels: list[AlertChannel] = []
        self._rules: list[AlertRule] = []
        self._suppression_seconds = suppression_seconds
        self._last_fired: dict[str, float] = {}

    def add_channel(self, channel: AlertChannel) -> None:
        self._channels.append(channel)

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def fire(self, severity: AlertSeverity, message: str, data: dict[str, Any] | None = None) -> None:
        """Send an alert to all channels."""
        key = f"{severity.value}:{message}"
        now = time.monotonic()

        if key in self._last_fired:
            if now - self._last_fired[key] < self._suppression_seconds:
                logger.debug(f"Alert suppressed: {message}")
                return

        self._last_fired[key] = now
        logger.info(f"ALERT [{severity.value}]: {message}")

        for channel in self._channels:
            try:
                channel.send(severity, message, data)
            except Exception as e:
                logger.error(f"Alert channel error: {e}")

    def check_rules(self) -> None:
        """Evaluate all rules and fire alerts for triggered conditions."""
        for rule in self._rules:
            try:
                if rule.condition():
                    data = rule.data_fn() if rule.data_fn else None
                    self.fire(rule.severity, rule.message_template, data)
            except Exception as e:
                logger.error(f"Alert rule '{rule.name}' error: {e}")
