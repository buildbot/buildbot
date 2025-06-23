# from twisted.trial import unittest

# Gerrit builds are sorted alphabetically
from buildbot.reporters.generators.gerrit import (
    GerritBuildEndStatusGenerator,
    GerritBuildSetStatusGenerator,
    GerritBuildStartStatusGenerator,
)

# Define a sample callback
def dummy_callback(event):
    if event['type'] == 'buildStarted':
        return f"👷 Build {event['builderName']} started for change {event['change']['id']}."
    elif event['type'] == 'buildFinished':
        status = event.get('buildStatus', 'unknown')
        return f"🏁 Build finished with status: {status}"
    elif event['type'] == 'buildSetFinished':
        return "📦 Build set finished"
    return None

def test_build_start_callback():
    generator = GerritBuildStartStatusGenerator(callback=dummy_callback)
    event = {
        'type': 'buildStarted',
        'builderName': 'my-builder',
        'change': {'id': 42},
    }
    result = generator.getMessage(event)
    assert "👷 Build my-builder started for change 42." == result

def test_build_end_callback():
    generator = GerritBuildEndStatusGenerator(callback=dummy_callback)
    event = {
        'type': 'buildFinished',
        'builderName': 'my-builder',
        'buildStatus': 'success',
    }
    result = generator.getMessage(event)
    assert result == "🏁 Build finished with status: success"

def test_build_set_callback():
    generator = GerritBuildSetStatusGenerator(callback=dummy_callback)
    event = {
        'type': 'buildSetFinished',
    }
    result = generator.getMessage(event)
    assert result == "📦 Build set finished"

def test_unknown_event_type_returns_none():
    generator = GerritBuildEndStatusGenerator(callback=dummy_callback)
    event = {
        'type': 'randomOtherThing',
    }
    result = generator.getMessage(event)
    assert result is None

def test_no_callback_returns_none():
    generator = GerritBuildEndStatusGenerator()
    event = {
        'type': 'buildFinished',
        'buildStatus': 'success',
    }
    result = generator.getMessage(event)
    assert result is None
