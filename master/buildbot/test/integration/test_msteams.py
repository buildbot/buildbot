from __future__ import annotations

from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.msteams import MsTeamsMessageFormatter
from buildbot.reporters.msteams import MsTeamsStatusPush


class FakeConfig:
    title = "Example Buildbot"
    buildbotURL = "https://buildbot.example/"


class FakeMaster:
    config = FakeConfig()
    httpservice = object()


class FakeResponse:
    code = 200

    def content(self) -> defer.Deferred[bytes]:
        return defer.succeed(b"ok")


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, path: str, json: dict[str, Any]) -> defer.Deferred[FakeResponse]:
        self.calls.append((path, json))
        return defer.succeed(FakeResponse())


class MsTeamsStatusPushTest(unittest.TestCase):
    def make_build(
        self, results: int = SUCCESS, steps: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        if steps is None:
            steps = [{"name": "compile", "results": SUCCESS}]

        return {
            "buildid": 101,
            "number": 42,
            "results": results,
            "state_string": "tests failed" if results == FAILURE else "",
            "builder": {"name": "linux-x86_64", "builderid": 7},
            "properties": {"workername": ("worker1", "test")},
            "buildset": {
                "sourcestamps": [
                    {
                        "branch": "main",
                        "revision": "abc123",
                        "patch": None,
                        "codebase": "",
                        "project": "demo",
                    }
                ]
            },
            "steps": steps,
        }

    @defer.inlineCallbacks
    def test_default_formatter_includes_instance_build_status_and_failed_step(self) -> Any:
        formatter = MsTeamsMessageFormatter()
        build = self.make_build(
            results=FAILURE,
            steps=[
                {"name": "checkout", "results": SUCCESS},
                {"name": "test", "results": FAILURE},
            ],
        )

        msg = yield formatter.format_message_for_build(FakeMaster(), build, mode=("failing",))

        self.assertEqual(msg["subject"], "BUILD FAILED: tests failed")
        self.assertIn("Instance: Example Buildbot (https://buildbot.example/)", msg["body"])
        self.assertIn(
            "Build: linux-x86_64 #42 (https://buildbot.example/#/builders/7/builds/42)",
            msg["body"],
        )
        self.assertIn(
            "Status: BUILD FAILED: tests failed (https://buildbot.example/#/builders/7/builds/42)",
            msg["body"],
        )
        self.assertIn("Failed step: test", msg["body"])

    @defer.inlineCallbacks
    def test_custom_template_can_reference_failed_step(self) -> Any:
        formatter = MsTeamsMessageFormatter(
            template="{% if failed_step %}Failed step: {{ failed_step['name'] }}{% endif %}"
        )
        build = self.make_build(
            results=FAILURE,
            steps=[
                {"name": "checkout", "results": SUCCESS},
                {"name": "lint", "results": FAILURE},
            ],
        )

        msg = yield formatter.format_message_for_build(FakeMaster(), build, mode=("failing",))

        self.assertEqual(msg["body"], "Failed step: lint")

    @defer.inlineCallbacks
    def test_send_message_wraps_card_in_teams_message_payload(self) -> Any:
        reporter = MsTeamsStatusPush(webhook_url="https://teams.example/webhook")
        reporter.card_config = {}
        reporter._http = FakeHttp()

        yield reporter.sendMessage(
            [
                {
                    "subject": "Build succeeded!",
                    "body": "Instance: Example Buildbot (https://buildbot.example/)",
                    "results": SUCCESS,
                    "builds": [self.make_build()],
                }
            ]
        )

        self.assertEqual(len(reporter._http.calls), 1)
        path, payload = reporter._http.calls[0]
        self.assertEqual(path, "")
        self.assertEqual(payload["type"], "message")
        self.assertEqual(payload["attachments"][0]["contentType"], "application/vnd.microsoft.card.adaptive")
        self.assertEqual(payload["attachments"][0]["content"]["type"], "AdaptiveCard")
        self.assertEqual(payload["attachments"][0]["content"]["body"][0]["text"], "Build succeeded!")
