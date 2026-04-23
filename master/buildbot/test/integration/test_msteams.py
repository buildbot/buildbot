import pytest

from twisted.internet import defer

from buildbot.reporters.msteams import MsTeamsStatusPush

class DummyBuild:
    def __init__(self, number=1, url="http://buildbot/build/1", project="demo", project_url="http://buildbot/project/demo", results_text="success", revision="abc123", triggered_by=None):
        self.data = {
            "number": number,
            "url": url,
            "project": project,
            "project_url": project_url,
            "results_text": results_text,
            "revision": revision,
            "triggered_by": triggered_by,
        }
    def get(self, key, default=None):
        return self.data.get(key, default)

class DummyMaster:
    pass

@pytest.inlineCallbacks
@defer.inlineCallbacks
def test_adaptive_card_default(monkeypatch):
    sent = {}
    def fake_post(url, headers, data):
        sent['url'] = url
        sent['headers'] = headers
        sent['data'] = data
        class Resp: pass
        return Resp()
    monkeypatch.setattr("buildbot.reporters.msteams.requests.post", fake_post)
    reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook")
    build = DummyBuild()
    yield reporter.buildFinished(build, None, DummyMaster())
    assert sent['url'] == "http://example.com/webhook"
    assert 'AdaptiveCard' in sent['data']
    assert 'The build #1 (http://buildbot/build/1)' in sent['data']

@pytest.inlineCallbacks
@defer.inlineCallbacks
def test_adaptive_card_custom_template(monkeypatch):
    sent = {}
    def fake_post(url, headers, data):
        sent['url'] = url
        sent['headers'] = headers
        sent['data'] = data
        class Resp: pass
        return Resp()
    monkeypatch.setattr("buildbot.reporters.msteams.requests.post", fake_post)
    custom_template = "Build {{ build['number'] }} for {{ project }}."
    reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook", body_template=custom_template)
    build = DummyBuild(number=42, project="testproj")
    yield reporter.buildFinished(build, None, DummyMaster())
    assert 'Build 42 for testproj.' in sent['data']

@pytest.inlineCallbacks
@defer.inlineCallbacks
def test_adaptive_card_error(monkeypatch, caplog):
    def fake_post(url, headers, data, timeout=10):
        class Resp:
            status_code = 500
            text = "Internal Server Error"
        return Resp()
    monkeypatch.setattr("buildbot.reporters.msteams.requests.post", fake_post)
    reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook")
    build = DummyBuild()
    with caplog.at_level("ERROR"):
        yield reporter.buildFinished(build, None, DummyMaster())
        assert any("Failed to send card" in r for r in caplog.text.splitlines())
