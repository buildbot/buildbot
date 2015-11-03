### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = '~1.4.1'

gulp = require('gulp')
require("shelljs/global")

gulp.task "publish", ['default'], ->
    rm "-rf", "buildbot-data-js"
    exec "git clone git@github.com:buildbot/buildbot-data-js.git"
    bower_json =
        name: "buildbot-data"
        version: "1.0.15"
        main: ["scripts.js"]
        moduleType: [],
        license: "MIT",
        ignore: []
        description: "Buildbot middleware to access data api"
        dependencies: {}
    cd "buildbot-data-js"
    exec("git reset --hard origin/master")
    cp "-rf", "../dist", "."
    cp "-rf", "../README.md", "."
    JSON.stringify(bower_json, null, "  ").to("bower.json")
    exec("git add .")
    exec("git commit -m " + bower_json.version)
    exec("git tag " + bower_json.version)
    exec("git push origin master")
    exec("git push origin " + bower_json.version)


config =

    ### ###########################################################################################
    #   Name of the module
    ### ###########################################################################################
    name: 'bbData'

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'dist'

    sourcemaps: true
    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        deps:
            tabex:
                version: '~1.0.3'
                files: 'dist/tabex.js'
            dexie:
                version: '~1.1.0'
                files: 'dist/latest/Dexie.js'
        testdeps:
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            'angular-mocks':
                version: ANGULAR_TAG
                files: 'angular-mocks.js'
    # as angular is a test deps, the tests need to be loaded first!
    karma:
        files: [ "tests.js", "scripts.js"]

    ngclassify: (config) ->
        return {
            appName: config.name
            provider:
              suffix: 'Service'
        }

    buildtasks: ['scripts', 'vendors', 'tests']

module.exports = config
