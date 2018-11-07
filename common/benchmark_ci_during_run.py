#!/usr/bin/env python

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

from __future__ import absolute_import
from __future__ import print_function

import argparse
import datetime
import os
import sys
import subprocess
import time

from twisted.internet import defer
from twisted.internet import reactor


def minibench():
    start = time.time()
    for i in range(0, 10000000):
        pass
    end = time.time()
    return end - start


def sleep_for_seconds(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d


@defer.inlineCallbacks
def run_minibench(period):
    while True:
        yield sleep_for_seconds(period)
        result = minibench()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        msg = '{0} minibench {1:.6} ms'.format(now, result * 1000)
        print(msg)


@defer.inlineCallbacks
def run_top(initial_wait, period):
    yield sleep_for_seconds(initial_wait)
    while True:
        subprocess.check_call(['top', '-n', '1'], stdout=sys.stdout)
        yield sleep_for_seconds(period)


@defer.inlineCallbacks
def stop_reactor_after_timeout(timeout):
    yield sleep_for_seconds(timeout)
    print('Exit due to timeout')
    reactor.stop()


def main():
    parser = argparse.ArgumentParser(prog='benchmark_ci_during_run')
    parser.add_argument('--minibench_period', type=int, default=10,
                        help="Duration between minibench invocations")
    parser.add_argument('--top_period', type=int, default=100,
                        help="Duration between top invocations")
    parser.add_argument('--start_top_after', type=int, default=1200,
                        help="Duration between top invocations")
    parser.add_argument('--timeout', type=int, default=2400,
                        help="Maximum duration to run the script")
    args = parser.parse_args()

    if 'HYPER_SIZE' not in os.environ:
        return

    reactor.callLater(0, run_minibench, args.minibench_period)
    reactor.callLater(0, run_top, args.start_top_after, args.top_period)
    reactor.callLater(0, stop_reactor_after_timeout, args.timeout)
    reactor.run()


if __name__ == '__main__':
    main()
