
import os

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

    graph_data = [
        {'x': 1, 'y': 100},
        {'x': 2, 'y': 200},
        {'x': 3, 'y': 300},
        {'x': 4, 'y': 0},
        {'x': 5, 'y': 100},
        {'x': 6, 'y': 200},
        {'x': 7, 'y': 300},
        {'x': 8, 'y': 0},
        {'x': 9, 'y': 100},
        {'x': 10, 'y': 200},
    ]

    # mydashboard.html is a template inside the template directory
    return render_template('mydashboard.html', builders=builders, builds=builds,
                           graph_data=graph_data)


# Here we assume c['www']['plugins'] has already be created earlier.
# Please see the web server documentation to understand how to configure
# the other parts.
# This is a list of dashboards, you can create several
c['www']['plugins']['wsgi_dashboards'] = [
    {
        'name': 'mydashboard',  # as used in URLs
        'caption': 'My Dashboard',  # Title displayed in the UI'
        'app': mydashboardapp,
        # priority of the dashboard in the left menu (lower is higher in the
        # menu)
        'order': 5,
        # An available icon list can be found at http://fontawesome.io/icons/. Double-check
        # the buildbot about dashboard for the installed version of Font Awesome as the
        # published icons may include more recently additions.
        'icon': 'area-chart'
    }
]
