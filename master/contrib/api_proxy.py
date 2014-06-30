import argparse
import flask
import os
import requests

from buildbot.www.service import WWWService
from flask import Response
from flask import request
from flask import stream_with_context

master_service = WWWService(None)

main_dir = master_service.apps['base'].static_dir

application = flask.Flask(__name__, static_url_path='', static_folder=main_dir)

for k, v in master_service.apps.items():
    if k != "base":
        try:
            os.symlink(v.static_dir, os.path.join(main_dir, k))
        except OSError:
            pass


def get_url():
    global args
    url = request.url
    url = url.replace("http://localhost:8010", args.dest_buildbot)
    return url


def reroute_stream(url):
    req = requests.get(get_url(), stream=True)
    return Response(stream_with_context(req.iter_content()), content_type=req.headers['content-type'])

application.route('/sse/<path:url>')(reroute_stream)
# application.route('/auth/<path:url>')(reroute_stream)


cache = {}


@application.route('/api/<path:url>')
def reroute_cache(url):
    if url not in cache:
        req = requests.get(get_url())
        cache[url] = req.content, req.headers['content-type']

    res = cache[url]
    return Response(res[0], content_type=res[1])


@application.route('/config.js')
def config():
    plugins = dict((k, {}) for k in master_service.apps if k != "base")
    return ('this.config = {"avatar_methods": {"name": "gravatar"}, "user": {"anonymous": true}, ' +
            '"plugins": %r, "url": "http://localhost:8010/", "port": 8010, "auth": {"name": "NoAuth"}}' % (plugins, ))


@application.route('/')
def root():
    return application.send_static_file('index.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='api proxy for web ui development.')
    parser.add_argument('--dest_buildbot', dest='dest_buildbot', help='url to the destination buildbot',
                        default="http://nine.buildbot.buildbot.net")
    args = parser.parse_args()
    application.run(host='0.0.0.0', port=8010, processes=10)
