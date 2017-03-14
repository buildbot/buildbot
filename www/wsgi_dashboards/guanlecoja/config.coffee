### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.5.3"
module.exports =

    ### ###########################################################################################
    #   Name of the plugin
    ### ###########################################################################################
    name: 'wsgi_dashboards'
    dir: build: 'buildbot_wsgi_dashboards/static'
    bower:
        testdeps:
            # vendors.js includes jquery, angularjs, etc in the right order
            "guanlecoja-ui":
                version: '~1.6.0'
                files: ['vendors.js', 'scripts.js']
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"
    karma:
        # we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js']
