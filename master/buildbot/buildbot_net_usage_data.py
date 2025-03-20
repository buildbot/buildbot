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
It uses urllib instead of requests in order to avoid requiring another dependency for statistics
feature.
urllib supports http_proxy already. urllib is blocking and thus everything is done from a thread.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import platform
import socket
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from twisted.internet import threads
from twisted.python import log

from buildbot.process.buildstep import _BuildStepFactory
from buildbot.util import unicode2bytes
from buildbot.www.config import get_environment_versions

# This can't change! or we will need to make sure we are compatible with all
# released version of buildbot >=0.9.0
PHONE_HOME_URL = "https://events.buildbot.net/events/phone_home"


def linux_distribution() -> tuple[str, str]:
    os_release = "/etc/os-release"
    meta_data = {}
    if os.path.exists(os_release):
        with open("/etc/os-release", encoding='utf-8') as f:
            for line in f:
                try:
                    k, v = line.strip().split("=")
                    meta_data[k] = v.strip('"')
                except Exception:
                    pass

    linux_id = meta_data.get("ID", "unknown_linux")

    linux_version = "unknown_version"
    # Pre-release versions of Debian contain VERSION_CODENAME but not VERSION_ID
    for version_key in ["VERSION_ID", "VERSION_CODENAME"]:
        linux_version = meta_data.get(version_key, linux_version)

    return linux_id, linux_version


def get_distro() -> str:
    system = platform.system()
    if system == "Linux":
        linux_dist = linux_distribution()
        return f"{linux_dist[0]}:{linux_dist[1]}"
    elif system == "Windows":
        win_dist: Any = platform.win32_ver()
        return f"{win_dist[0]}:{win_dist[1]}"
    elif system == "Java":
        java_dist: Any = platform.java_ver()
        return f"{java_dist[0]}:{java_dist[1]}"
    elif system == "Darwin":
        mac_dist: Any = platform.mac_ver()
        return f"{mac_dist[0]}"
    # else:
    return ":".join(platform.uname()[0:1])


def getName(obj: Any) -> str:
    """This method finds the first parent class which is within the buildbot namespace
    it prepends the name with as many ">" as the class is subclassed
    """

    # elastic search does not like '.' in dict keys, so we replace by /
    def sanitize(name: str) -> str:
        return name.replace(".", "/")

    if isinstance(obj, _BuildStepFactory):
        klass = obj.step_class
    else:
        klass = type(obj)
    name = ""
    klasses = (klass, *inspect.getmro(klass))
    for klass in klasses:
        if hasattr(klass, "__module__") and klass.__module__.startswith("buildbot."):
            return sanitize(name + klass.__module__ + "." + klass.__name__)
        else:
            name += ">"
    return sanitize(type(obj).__name__)


def countPlugins(plugins_uses: dict[str, int], lst: dict[str, Any] | list[Any]) -> None:
    items: list[Any] = list(lst.values()) if isinstance(lst, dict) else lst
    for i in items:
        name = getName(i)
        plugins_uses.setdefault(name, 0)
        plugins_uses[name] += 1


def basicData(master: Any) -> dict[str, Any]:
    plugins_uses: dict[str, int] = {}
    countPlugins(plugins_uses, master.config.workers)
    countPlugins(plugins_uses, master.config.builders)
    countPlugins(plugins_uses, master.config.schedulers)
    countPlugins(plugins_uses, master.config.services)
    countPlugins(plugins_uses, master.config.change_sources)
    for b in master.config.builders:
        countPlugins(plugins_uses, b.factory.steps)

    # we hash the master's name + various other master dependent variables
    # to get as much as possible an unique id
    # we hash it to not leak private information about the installation such as hostnames and domain
    # names
    hashInput = (
        master.name  # master name contains hostname + master basepath
        + socket.getfqdn()  # we add the fqdn to account for people
        # call their buildbot host 'buildbot'
        # and install it in /var/lib/buildbot
    )
    hashInput = unicode2bytes(hashInput)
    installid = hashlib.sha1(hashInput).hexdigest()
    return {
        'installid': installid,
        'versions': dict(get_environment_versions()),
        'platform': {
            'platform': platform.platform(),
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_implementation': platform.python_implementation(),
            # xBSD including osx will disclose too much information after [4] like where it
            # was built
            'version': " ".join(platform.version().split(' ')[:4]),
            'distro': get_distro(),
        },
        'plugins': plugins_uses,
        'db': master.config.db.db_url.split("://")[0],
        'mq': master.config.mq['type'],
        'www_plugins': list(master.config.www['plugins'].keys()),
    }


def fullData(master: Any) -> dict[str, list[list[str]]]:
    """
    Send the actual configuration of the builders, how the steps are agenced.
    Note that full data will never send actual detail of what command is run, name of servers,
    etc.
    """

    builders = []
    for b in master.config.builders:
        steps = []
        for step in b.factory.steps:
            steps.append(getName(step))
        builders.append(steps)
    return {'builders': builders}


def computeUsageData(master: Any) -> dict[str, Any] | None:
    if master.config.buildbotNetUsageData is None:
        return None
    data = basicData(master)

    if master.config.buildbotNetUsageData != "basic":
        data.update(fullData(master))

    if callable(master.config.buildbotNetUsageData):
        data = master.config.buildbotNetUsageData(data)

    return data


def _sendWithUrlib(url: str, data: dict[str, Any]) -> bytes | None:
    encoded_data = json.dumps(data).encode()
    clen = len(encoded_data)
    req = urllib_request.Request(
        url, encoded_data, {'Content-Type': 'application/json', 'Content-Length': str(clen)}
    )
    try:
        f = urllib_request.urlopen(req)
    except urllib_error.URLError:
        return None
    res = f.read()
    f.close()
    return res


def _sendWithRequests(url: str, data: dict[str, Any]) -> str | None:
    try:
        import requests  # pylint: disable=import-outside-toplevel
    except ImportError:
        return None
    r = requests.post(url, json=data, timeout=30)
    return r.text


def _sendBuildbotNetUsageData(data: dict[str, Any]) -> None:
    log.msg(f"buildbotNetUsageData: sending {data}")
    # first try with requests, as this is the most stable http library
    res: str | bytes | None = _sendWithRequests(PHONE_HOME_URL, data)
    # then we try with stdlib, which not always work with https
    if res is None:
        res = _sendWithUrlib(PHONE_HOME_URL, data)
    # at last stage
    if res is None:
        log.msg(
            "buildbotNetUsageData: Could not send using https, "
            "please `pip install 'requests[security]'` for proper SSL implementation`"
        )
        data['buggySSL'] = True
        res = _sendWithUrlib(PHONE_HOME_URL.replace("https://", "http://"), data)

    log.msg("buildbotNetUsageData: buildbot.net said:", res)


def sendBuildbotNetUsageData(master: Any) -> None:
    if master.config.buildbotNetUsageData is None:
        return
    data = computeUsageData(master)
    if data is None:
        return
    threads.deferToThread(_sendBuildbotNetUsageData, data)
