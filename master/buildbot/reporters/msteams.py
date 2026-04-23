# Copyright Buildbot Team Members
# SPDX-License-Identifier: GPL-2.0-only
import json
import time
from typing import Any
from typing import Optional

import requests

from twisted.python import log

import treq

from buildbot.reporters.base import ReporterBase
from buildbot.reporters.message import MessageFormatterBaseJinja


class MsTeamsStatusPush(ReporterBase):
    name: str = "MsTeamsStatusPush"
    _last_sent: float = 0.0
    _rate_limit_seconds: int = 5

    def __init__(
        self,
        webhook_url: str,
        body_template: Optional[str] = None,
        card_config: Optional[dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.webhook_url: str = webhook_url
        self.body_template: str = body_template or self.default_body_template()
        self.card_config: dict[str, Any] = card_config or {}
        self.formatter: MessageFormatterBaseJinja = MessageFormatterBaseJinja(template=self.body_template, template_type="plain")

    @staticmethod
    def default_body_template() -> str:
        return (
            "The build #{{ build['number'] }} ({{ build_url }}) for project {{ project }}"
            "{% if project_url %} ({{ project_url }}){% endif %} has {{ results_text }}.\n"
            "Commit: {{ revision }}\n"
            "{% if build['triggered_by'] %}Triggered by: {{ build['triggered_by'] }}{% endif %}"
        )

    @inlineCallbacks
    def buildFinished(self, build: Any, results: Any, master: Any, **kwargs: Any) -> Any:
        """Send notification to MS Teams when a build finishes."""
        context = self._get_context(build, results, master)
        msgdict = yield self.formatter.render_message_dict(master, context)
        card = self._make_adaptive_card(msgdict)
        log.msg(f"MsTeamsStatusPush: Sending notification for build {build.get('number')}")
        yield self._send_to_teams_async(card)

    def _get_context(self, build: Any, results: Any, master: Any) -> dict[str, Any]:
        # This should be expanded to match Buildbot's context for templates
        return {
            "build": build,
            "build_url": build.get("url"),
            "project": build.get("project"),
            "project_url": build.get("project_url"),
            "results_text": build.get("results_text"),
            "revision": build.get("revision"),
        }

    def _make_adaptive_card(self, msgdict: dict[str, Any]) -> dict[str, Any]:
        card = {
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": msgdict["subject"] or "Buildbot Notification"},
                {"type": "TextBlock", "text": msgdict["body"], "wrap": True},
            ],
        }
        card.update(self.card_config)
        return card

    # Removed synchronous _send_to_teams; all notifications are now async

    @inlineCallbacks
    def _send_to_teams_async(self, card: dict[str, Any]) -> None:
        """Send the Adaptive Card to MS Teams asynchronously using treq."""
        try:
            response = yield treq.post(self.webhook_url, json=card, headers={"Content-Type": "application/json"})
            text = yield response.text()
            if response.code >= 400:
                log.err(f"MsTeamsStatusPush: Failed to send card, status {response.code}, response: {text}")
            else:
                log.msg("MsTeamsStatusPush: Notification sent successfully (async).")
        except Exception as e:
            log.err(f"MsTeamsStatusPush: Exception sending card (async): {e}")

    @inlineCallbacks
    def buildStarted(self, build: Any, results: Any, master: Any, **kwargs: Any) -> Any:
        """Send notification to MS Teams when a build starts."""
        context = self._get_context(build, results, master)
        msgdict = yield self.formatter.render_message_dict(master, context)
        card = self._make_adaptive_card(msgdict)
        log.msg(f"MsTeamsStatusPush: Sending start notification for build {build.get('number')}")
        yield self._send_to_teams_async(card)
