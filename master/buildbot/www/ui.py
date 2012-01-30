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

import os
from twisted.python import util
from buildbot.www import resource

html = """\
<!DOCTYPE html>
<html>
    <head>
        <title></title>
        <link rel="stylesheet" type="text/css"
              href="%(baseurl)sstatic/css/default.css" />
        <script src="http://code.jquery.com/jquery-1.7.2.min.js" />
        <script src="http://ajax.cdnjs.com/ajax/libs/json2/20110223/json2.js" />
        <script type="text/javascript">
            bb.baseurl = "%(baseurl)s";
        </script>
        <script type="text/javascript">
$(function() {
    var ws_url = "%(baseurl)s".replace(/^http:/, "ws:");
    console.log(ws_url);
    var ws = new WebSocket(ws_url + "ws");
    ws.onopen = function() {
      console.log("onopen");
      $('#status').text('open');
      // this must be delaeyed at least until after the onopen has returned, or
      // on firefox the message isn't sent until it gets flushed.  WebSockets
      // are still fresh and exciting, eh?
      window.setTimeout(function() {
        ws.send(JSON.stringify({req: 'startConsuming',
                              path: [ 'change' ],
                              options: {}}));
        $('#status').text('subscribed');
      }, 0);
    };
    ws.onmessage = function (e) {
      console.log("onmessage", e.data);
      $('#message').text(e.data);
    };
    ws.onerror = function (e) {
      console.log("onmessage", e);
      $('#info').text(e.data);
    };
    ws.onclose = function() {
      console.log("onclose");
      $('#status').text('closed');
    };
});
        </script>
    </head>
  <body class="interface">

    <div id="header" class="header">
    </div>
    <hr />
    <div id="content" class="content">
        MESSAGE:
        <div id="message"></div>
        INFO:
        <div id="info"></div>
        STATUS:
        <div id="status"></div>
    </div>
    </body>
</html>
"""

class UIResource(resource.Resource):
    isLeaf = True

    def __init__(self, master):
        resource.Resource.__init__(self, master)

        self.jsdir = os.path.join(util.sibpath(__file__, 'static'), 'js')

    def render(self, request):
        contents = dict(
            baseurl = self.baseurl)
        return html % contents
