# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.trial import unittest

from buildbot.scripts import devproxy

# This string has the script containing the configuration right before the closing html tag.
test_html_string_1 = '''</script><script>angular.module("buildbot_config", []).constant("config"'''\
    ''', {"user": {"anonymous": true}, "port": "tcp:8010:interface=192.168.80.239", "plugins":'''\
    ''' {"console_view": true, "waterfall_view": {}, "react_console_view": {}}, "auth": {"name": '''\
    '''"GitHub", "oauth2": true, "fa_icon": "fa-github", "autologin": false}, "authz": {}, '''\
    '''"avatar_methods": {"name": "gravatar"}, "logfileName": "http.log", "versions": [["Python", '''\
    '''"3.6.6"], ["Buildbot", "2.3.1-dev98"], ["Twisted", "18.9.0"], ["buildbot_travis", "0.6.4.dev5"]'''\
    ''', ["buildbot-codeparameter", "1.6.1.dev196"]], "ui_default_config": {"Waterfall.scaling_waterfall"'''\
    ''': 0.19753086419753088, "Builders.show_old_builders": true, "Builders.buildFetchLimit": 1000}'''\
    ''', "buildbotURL": "http://localhost:8011/", "title": "buildbot travis", "titleURL": '''\
    '''"http://buildbot.net/", "multiMaster": true, "buildbotURLs": ["http://localhost:8011/", '''\
    '''"https://buildbot.buildbot.net/"]})</script></html>'''

# This string has more scripts after the script containing the configuration.
test_html_string_2 = '''</script><script>angular.module("buildbot_config", []).constant("config"'''\
    ''', {"user": {"anonymous": true}, "port": "tcp:8010:interface=192.168.80.239", "plugins":'''\
    ''' {"console_view": true, "waterfall_view": {}, "react_console_view": {}}, "auth": {"name": '''\
    '''"GitHub", "oauth2": true, "fa_icon": "fa-github", "autologin": false}, "authz": {}, '''\
    '''"avatar_methods": {"name": "gravatar"}, "logfileName": "http.log", "versions": [["Python", '''\
    '''"3.6.6"], ["Buildbot", "2.3.1-dev98"], ["Twisted", "18.9.0"], ["buildbot_travis", "0.6.4.dev5"]'''\
    ''', ["buildbot-codeparameter", "1.6.1.dev196"]], "ui_default_config": {"Waterfall.scaling_waterfall"'''\
    ''': 0.19753086419753088, "Builders.show_old_builders": true, "Builders.buildFetchLimit": 1000}'''\
    ''', "buildbotURL": "http://localhost:8011/", "title": "buildbot travis", "titleURL": '''\
    '''"http://buildbot.net/", "multiMaster": true, "buildbotURLs": ["http://localhost:8011/", '''\
    '''"https://buildbot.buildbot.net/"]})</script><script>etcetera...'''


class TestStatusLog(unittest.TestCase):

    def test_devproxy_json_extraction_1(self):
        config = devproxy.extract_config_from_html(test_html_string_1)
        print(config)
        self.assertEqual(config["plugins"]["console_view"], True)

    def test_devproxy_json_extraction_2(self):
        config = devproxy.extract_config_from_html(test_html_string_2)
        print(config)
        self.assertEqual(config["plugins"]["console_view"], True)
