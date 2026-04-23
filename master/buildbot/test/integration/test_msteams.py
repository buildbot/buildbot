
from twisted.trial import unittest
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

class MsTeamsStatusPushTest(unittest.TestCase):
    @defer.inlineCallbacks
    def test_adaptive_card_default(self):
        sent = {}
        def fake_post(url, headers, data):
            sent['url'] = url
            sent['headers'] = headers
            sent['data'] = data
            class Resp: pass
            return Resp()
        import buildbot.reporters.msteams as msteams_mod
        self.patch(msteams_mod.requests, "post", fake_post)
        reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook")
        build = DummyBuild()
        yield reporter.buildFinished(build, None, DummyMaster())
        self.assertEqual(sent['url'], "http://example.com/webhook")
        self.assertIn('AdaptiveCard', sent['data'])
        self.assertIn('The build #1 (http://buildbot/build/1)', sent['data'])

    @defer.inlineCallbacks
    def test_adaptive_card_custom_template(self):
        sent = {}
        def fake_post(url, headers, data):
            sent['url'] = url
            sent['headers'] = headers
            sent['data'] = data
            class Resp: pass
            return Resp()
        import buildbot.reporters.msteams as msteams_mod
        self.patch(msteams_mod.requests, "post", fake_post)
        custom_template = "Build {{ build['number'] }} for {{ project }}."
        reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook", body_template=custom_template)
        build = DummyBuild(number=42, project="testproj")
        yield reporter.buildFinished(build, None, DummyMaster())
        self.assertIn('Build 42 for testproj.', sent['data'])

    @defer.inlineCallbacks
    def test_adaptive_card_error(self):
        sent = {}
        def fake_post(url, headers, data, timeout=10):
            sent['url'] = url
            sent['headers'] = headers
            sent['data'] = data
            class Resp:
                status_code = 500
                text = "Internal Server Error"
            return Resp()
        import buildbot.reporters.msteams as msteams_mod
        self.patch(msteams_mod.requests, "post", fake_post)
        reporter = MsTeamsStatusPush(webhook_url="http://example.com/webhook")
        build = DummyBuild()
        # Simulate error logging by capturing log.err output
        from twisted.python import log as twisted_log
        import io
        log_stream = io.StringIO()
        observer = twisted_log.FileLogObserver(log_stream)
        twisted_log.addObserver(observer.emit)
        try:
            yield reporter.buildFinished(build, None, DummyMaster())
        finally:
            twisted_log.removeObserver(observer.emit)
        log_contents = log_stream.getvalue()
        self.assertIn("Failed to send card", log_contents)
