from __future__ import annotations

# Copyright Buildbot Team Members
# SPDX-License-Identifier: GPL-2.0-only

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.message import MessageFormatterEmpty
from buildbot.util import httpclientservice

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType

DEFAULT_BODY_TEMPLATE = """\
Instance: {{ buildbot_title }} ({{ buildbot_url }})
Build: {{ buildername }} #{{ build['number'] }} ({{ build_url }})
Status: {{ summary }} ({{ build_url }})
{% if failed_step %}Failed step: {{ failed_step['name'] }}{% endif %}"""

DEFAULT_SUBJECT_TEMPLATE = "{{ summary }}"


def get_failed_step(build: dict[str, Any]) -> dict[str, Any] | None:
    if build['results'] not in (FAILURE, EXCEPTION):
        return None

    steps = build.get('steps', [])
    for result in (FAILURE, EXCEPTION):
        for step in steps:
            if step.get('results') == result:
                return step

    for step in steps:
        if step.get('results') != SUCCESS:
            return step

    return None


class MsTeamsMessageFormatter(MessageFormatter):
    def __init__(self, template: str | None = None) -> None:
        super().__init__(
            subject=DEFAULT_SUBJECT_TEMPLATE,
            template=template or DEFAULT_BODY_TEMPLATE,
            template_type='plain',
            want_steps=True,
        )

    def buildAdditionalContext(self, master: Any, ctx: dict[str, Any]) -> None:
        super().buildAdditionalContext(master, ctx)
        ctx['failed_step'] = get_failed_step(ctx['build'])


class MsTeamsStatusPush(ReporterBase):
    name: str | None = "MsTeamsStatusPush"

    def checkConfig(  # type: ignore[override]
        self,
        webhook_url: str,
        body_template: str | None = None,
        card_config: dict[str, Any] | None = None,
        debug: bool | None = None,
        verify: bool | None = None,
        generators: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(webhook_url, str):
            config.error("webhook_url must be a string")
        if body_template is not None and not isinstance(body_template, str):
            config.error("body_template must be a string")
        if card_config is not None and not isinstance(card_config, dict):
            config.error("card_config must be a dictionary")

        if generators is None:
            generators = self._create_default_generators(body_template)

        super().checkConfig(generators=generators, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        webhook_url: str,
        body_template: str | None = None,
        card_config: dict[str, Any] | None = None,
        debug: bool | None = None,
        verify: bool | None = None,
        generators: list[Any] | None = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        self.card_config = {} if card_config is None else dict(card_config)
        self.debug = debug
        self.verify = verify

        if generators is None:
            generators = self._create_default_generators(body_template)

        yield super().reconfigService(generators=generators, **kwargs)

        self._http = yield httpclientservice.HTTPSession(
            self.master.httpservice,
            webhook_url,
            headers={"Content-Type": "application/json"},
            debug=self.debug,
            verify=self.verify,
        )

    def _create_default_generators(self, body_template: str | None) -> list[Any]:
        return [
            BuildStartEndStatusGenerator(
                start_formatter=MessageFormatterEmpty(),
                end_formatter=MsTeamsMessageFormatter(template=body_template),
            )
        ]

    @defer.inlineCallbacks
    def sendMessage(self, reports: list[Any]) -> InlineCallbacksType[None]:
        report = reports[0]
        if report['body'] is None:
            return

        response = yield self._http.post("", json=self._create_message_payload(report))
        if response.code // 100 != 2:
            content = yield response.content()
            log.err(f"{response.code}: unable to send MS Teams notification: {content}")

    def _create_message_payload(self, report: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": self._create_card(report),
                }
            ],
        }

    def _create_card(self, report: dict[str, Any]) -> dict[str, Any]:
        body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": report['subject'] or "Buildbot notification",
                "wrap": True,
            }
        ]

        if report['body']:
            body.append({"type": "TextBlock", "text": report['body'], "wrap": True})

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
        }
        card.update(self.card_config)
        return card
