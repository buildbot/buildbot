import argparse
import flask
import json
import os
import requests

from buildbot.www.service import WWWService
from flask import Response
from flask import redirect
from flask import render_template
from flask import request
from flask import stream_with_context

master_service = WWWService(None)

main_dir = master_service.apps.base.static_dir
dest_buildbot = None
port = None
local_url = None

application = flask.Flask(__name__, static_url_path='', static_folder=main_dir, template_folder=main_dir)
for name in master_service.apps.names:
    if name != "base":
        plugin = master_service.apps.get(name)
        try:
            os.symlink(plugin.static_dir, os.path.join(main_dir, name))
        except OSError:
            pass


def get_url():
    url = request.url
    url = url.replace(local_url, dest_buildbot)
    return url


def reroute_stream(url=None):
    req = requests.get(get_url(), stream=True)
    return Response(stream_with_context(req.iter_content()), content_type=req.headers['content-type'])

application.route('/sse/<path:url>')(reroute_stream)
application.route('/avatar')(reroute_stream)
# application.route('/auth/<path:url>')(reroute_stream)


cache = {}


@application.route('/api/<path:url>')
def reroute_cache(url):
    if url not in cache:
        req = requests.get(get_url())
        cache[url] = req.content, req.headers['content-type']

    res = cache[url]
    return Response(res[0], content_type=res[1])


plugins = dict((k, {}) for k in master_service.apps.names if k != "base")
config = {
    "avatar_methods": {"name": "gravatar"},
    "user": {"anonymous": True},
    "plugins": plugins,
    "port": 8010,
    "auth": {"name": "NoAuth"}
}


@application.route('/')
def root():
    if local_url not in request.url:
        return redirect(local_url)
    return render_template('index.html', configjson=json.dumps(config), plugins=plugins)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='api proxy for web ui development.')
    parser.add_argument('--dest_buildbot',
                        dest='dest_buildbot',
                        help='url to the destination buildbot',
                        default="http://nine.buildbot.buildbot.net")
    parser.add_argument('--bind_port',
                        dest='bind_port',
                        type=int,
                        help='port to bind locally',
                        default="http://nine.buildbot.buildbot.net")

    args = parser.parse_args()
    dest_buildbot = args.dest_buildbot
    port = args.bind_port

    local_url = "http://127.0.0.1:{port}".format(port=port)
    application.run(host='127.0.0.1', port=port, processes=10)
