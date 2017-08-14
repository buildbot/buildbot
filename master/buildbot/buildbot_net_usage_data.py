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

"""
This files implement buildbotNetUsageData options
It uses urllib2 instead of requests in order to avoid requiring another dependency for statistics feature.
urllib2 supports http_proxy already urllib2 is blocking and thus everything is done from a thread.
"""

from __future__ import absolute_import
from __future__ import print_function
from future.moves.urllib import error as urllib_error
from future.moves.urllib import request as urllib_request

import hashlib
import inspect
import json
import os
import platform
import socket

from twisted.internet import threads
from twisted.python import log

from buildbot.process.buildstep import _BuildStepFactory
from buildbot.util import unicode2bytes
from buildbot.www.config import IndexResource

# This can't change! or we will need to make sure we are compatible with all
# released version of buildbot >=0.9.0
PHONE_HOME_URL = "https://events.buildbot.net/events/phone_home"


def linux_distribution():
    os_release = "/etc/os-release"
    meta_data = {'ID': "unknown_linux", 'VERSION_ID': "unknown_version"}
    if os.path.exists(os_release):
        with open("/etc/os-release") as f:
            for line in f:
                try:
                    k, v = line.strip().split("=")
                    meta_data[k] = v.strip('""')
                except Exception:
                    pass
    return meta_data['ID'], meta_data['VERSION_ID']


def get_distro():
    system = platform.system()
    if system == "Linux":
        dist = linux_distribution()
        return "{}:{}".format(dist[0], dist[1])
    elif system == "Windows":
        dist = platform.win32_ver()
        return "{}:{}".format(dist[0], dist[1])
    elif system == "Java":
        dist = platform.java_ver()
        return "{}:{}".format(dist[0], dist[1])
    elif system == "Darwin":
        dist = platform.mac_ver()
        return "{}".format(dist[0])
    # else:
    return ":".join(platform.uname()[0:1])


def getName(obj):
    """This method finds the first parent class which is within the buildbot namespace
    it prepends the name with as many ">" as the class is subclassed
    """
    # elastic search does not like '.' in dict keys, so we replace by /
    def sanitize(name):
        return name.replace(".", "/")
    if isinstance(obj, _BuildStepFactory):
        klass = obj.factory
    else:
        klass = type(obj)
    name = ""
    klasses = (klass, ) + inspect.getmro(klass)
    for klass in klasses:
        if hasattr(klass, "__module__") and klass.__module__.startswith("buildbot."):
            return sanitize(name + klass.__module__ + "." + klass.__name__)
        else:
            name += ">"
    return sanitize(type(obj).__name__)


def countPlugins(plugins_uses, lst):
    if isinstance(lst, dict):
        lst = lst.values()
    for i in lst:
        name = getName(i)
        plugins_uses.setdefault(name, 0)
        plugins_uses[name] += 1


def basicData(master):

    plugins_uses = {}
    countPlugins(plugins_uses, master.config.workers)
    countPlugins(plugins_uses, master.config.builders)
    countPlugins(plugins_uses, master.config.schedulers)
    countPlugins(plugins_uses, master.config.services)
    countPlugins(plugins_uses, master.config.change_sources)
    for b in master.config.builders:
        countPlugins(plugins_uses, b.factory.steps)

    # we hash the master's name + various other master dependent variables
    # to get as much as possible an unique id
    # we hash it to not leak private information about the installation such as hostnames and domain names
    hashInput = (
        master.name +  # master name contains hostname + master basepath
        socket.getfqdn()  # we add the fqdn to account for people
                          # call their buildbot host 'buildbot'
                          # and install it in /var/lib/buildbot
    )
    hashInput = unicode2bytes(hashInput)
    installid = hashlib.sha1(hashInput).hexdigest()
    return {
        'installid': installid,
        'versions': dict(IndexResource.getEnvironmentVersions()),
        'platform': {
            'platform': platform.platform(),
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_implementation': platform.python_implementation(),
            # xBSD including osx will disclose too much information after [4] like where it was built
            'version': " ".join(platform.version().split(' ')[:4]),
            'distro': get_distro()
        },
        'plugins': plugins_uses,
        'db': master.config.db['db_url'].split("://")[0],
        'mq': master.config.mq['type'],
        'www_plugins': list(master.config.www['plugins'].keys())
    }


def fullData(master):
    """
        Send the actual configuration of the builders, how the steps are agenced.
        Note that full data will never send actual detail of what command is run, name of servers, etc.
    """

    builders = []
    for b in master.config.builders:
        steps = []
        for step in b.factory.steps:
            steps.append(getName(step))
        builders.append(steps)
    return {'builders': builders}


def computeUsageData(master):
    if master.config.buildbotNetUsageData is None:
        return
    data = basicData(master)

    if master.config.buildbotNetUsageData != "basic":
        data.update(fullData(master))

    if callable(master.config.buildbotNetUsageData):
        data = master.config.buildbotNetUsageData(data)

    return data


def _sendWithUrlib(url, data):
    data = json.dumps(data).encode()
    clen = len(data)
    req = urllib_request.Request(url, data, {
        'Content-Type': 'application/json',
        'Content-Length': clen
    })
    try:
        f = urllib_request.urlopen(req)
    except urllib_error.URLError:
        return None
    res = f.read()
    f.close()
    return res


def _sendWithRequests(url, data):
    try:
        import requests
    except ImportError:
        return None
    r = requests.post(url, json=data)
    return r.text


def _sendBuildbotNetUsageData(data):
    log.msg("buildbotNetUsageData: sending {}".format(data))
    # first try with requests, as this is the most stable http library
    res = _sendWithRequests(PHONE_HOME_URL, data)
    # then we try with stdlib, which not always work with https
    if res is None:
        res = _sendWithUrlib(PHONE_HOME_URL, data)
    # at last stage
    if res is None:
        log.msg("buildbotNetUsageData: Could not send using https, "
                "please `pip install 'requests[security]'` for proper SSL implementation`")
        data['buggySSL'] = True
        res = _sendWithUrlib(PHONE_HOME_URL.replace("https://", "http://"), data)

    log.msg("buildbotNetUsageData: buildbot.net said:", res)


def sendBuildbotNetUsageData(master):
    if master.config.buildbotNetUsageData is None:
        return
    data = computeUsageData(master)
    if data is None:
        return
    threads.deferToThread(_sendBuildbotNetUsageData, data)
