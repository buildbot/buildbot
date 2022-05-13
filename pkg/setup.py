#!/usr/bin/env python
#
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

from setuptools import setup

import buildbot_pkg

setup(
    name="buildbot-pkg",
    version=buildbot_pkg.getVersion("."),
    description="Buildbot packaging tools",
    author="Pierre Tardy",
    author_email="tardyp@gmail.com",
    url="http://buildbot.net/",
    py_modules=["buildbot_pkg"],
    install_requires=[
        "setuptools >= 21.2.1",
    ],
    classifiers=["License :: OSI Approved :: GNU General Public License v2 (GPLv2)"],
)
