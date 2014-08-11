### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.2.0"

gulp = require("gulp")
require("shelljs/global")

gulp.task "publish", ['default'], ->
    if not exec "git diff --no-ext-diff --quiet --exit-code"
        echo "print commit your changes"
        return
    bower_json =
        name: "guanlecoja-ui"
        version: "1.0.2"
        main: ["scripts.js", "styles.css", "fonts/*", "img/*"]
        description: "Sets of widgets and integrated bower dependencies useful for dashboard SPAs"
        dependencies: {}

    exec("git checkout gh-pages")
    cp "-rf", "static/*", "."
    JSON.stringify(bower_json).to("bower.json")
    exec("git add .")
    exec("git commit -m " + bower_json.version)
    exec("git tag " + bower_json.version)
    exec("git push origin gh-pages")
    exec("git push origin " + bower_json.version)
    exec("git checkout master")


module.exports =

    ### ###########################################################################################
    #   Name of the module
    ### ###########################################################################################
    name: 'guanlecoja.ui'

    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'static'

    devserver:
        # development server port
        port: 8080

    sourcemaps: true

    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        deps:
            jquery:
                version: '~2.1.1'
                files: 'dist/jquery.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-bootstrap":
                version: '~0.11.0'
                files: 'ui-bootstrap-tpls.js'
            "angular-ui-router":
                version: '~0.2.10'
                files: 'release/angular-ui-router.js'
            "angular-recursion":
                version: '~1.0.1'
                files: 'angular-recursion.js'
            lodash:
                version: "~2.4.1"
                files: 'dist/lodash.js'
            'underscore.string':
                version: "~2.3.3"
                files: 'lib/underscore.string.js'
            "font-awesome":
                version: "~4.1.0"
                files: []
            "bootstrap":
                version: "~3.1.1"
                files: []
        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

