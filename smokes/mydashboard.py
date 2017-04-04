from __future__ import absolute_import
from __future__ import print_function

import os
import time

import requests
from flask import Flask
from flask import render_template

from buildbot.process.results import statusToString

mydashboardapp = Flask('test', root_path=os.path.dirname(__file__))
# this allows to work on the template without having to restart Buildbot
mydashboardapp.config['TEMPLATES_AUTO_RELOAD'] = True


@mydashboardapp.route("/index.html")
def main():
    # This code fetches build data from the data api, and give it to the
    # template
    builders = mydashboardapp.buildbot_api.dataGet("/builders")

    builds = mydashboardapp.buildbot_api.dataGet("/builds", limit=20)

    # properties are actually not used in the template example, but this is
    # how you get more properties
    for build in builds:
        build['properties'] = mydashboardapp.buildbot_api.dataGet(
            ("builds", build['buildid'], "properties"))

        build['results_text'] = statusToString(build['results'])

    # Example on how to use requests to get some info from other web servers
    code_frequency_url = "https://api.github.com/repos/buildbot/buildbot/stats/code_frequency"
    results = requests.get(code_frequency_url)
    while results.status_code == 202:
        # while github calculates statistics, it returns code 202.
        # this is no problem, we just sleep in our thread..
        time.sleep(500)
        results = requests.get(code_frequency_url)

    # some post processing of the data from github
    graph_data = []
    for i, data in enumerate(results.json()):
        graph_data.append(
            dict(x=data[0], y=data[1])
        )

    # mydashboard.html is a template inside the template directory
    return render_template('mydashboard.html', builders=builders, builds=builds,
                           graph_data=graph_data)


# Here we assume c['www']['plugins'] has already be created earlier.
# Please see the web server documentation to understand how to configure
# the other parts.
c['www']['plugins']['wsgi_dashboards'] = [  # This is a list of dashboards, you can create several
    {
        'name': 'mydashboard',  # as used in URLs
        'caption': 'My Dashboard',  # Title displayed in the UI'
        'app': mydashboardapp,
        # priority of the dashboard in the left menu (lower is higher in the
        # menu)
        'order': 5,
        # available icon list can be found at http://fontawesome.io/icons/
        'icon': 'area-chart'
    }
]
