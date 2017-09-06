### ###############################################################################################
#
#   This module contains all configuration for the build process
#
### ###############################################################################################
ANGULAR_TAG = "~1.5.3"

gulp = require("gulp")
require("shelljs/global")

gulp.task "publish", ['default'], ->
    rm "-rf", "guanlecoja-ui"
    exec "git clone git@github.com:buildbot/guanlecoja-ui.git"
    bower_json =
        name: "guanlecoja-ui"
        version: "1.7.0"
        main: ["scripts.js", "styles.css", "fonts/*", "img/*"]
        ignore: []
        description: "Sets of widgets and integrated bower dependencies useful for dashboard SPAs"
        dependencies: {}
    cd "guanlecoja-ui"
    exec("git reset --hard origin/gh-pages")
    cp "-rf", "../static/*", "."
    cp "-rf", "../README.md", "."
    JSON.stringify(bower_json, null, "  ").to("bower.json")
    exec("git add .")
    exec("git commit -m " + bower_json.version)
    exec("git tag " + bower_json.version)
    exec("git push origin HEAD:gh-pages")
    exec("git push origin " + bower_json.version)

gulp.task "readme", ->
    gulp.src("Readme.md").pipe gulp.dest(config.dir.build)

config =

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
    vendors_apart: true
    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        deps:
            jquery:
                version: '~2.2.3'
                files: 'dist/jquery.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-bootstrap":
                version: '~1.1.0'
                files: 'ui-bootstrap-tpls.js'
            "angular-ui-router":
                version: '~0.2.18'
                files: 'release/angular-ui-router.js'
            "angular-recursion":
                version: '~1.0.5'
                files: 'angular-recursion.js'
            lodash:
                version: "~4.11.1"
                files: 'dist/lodash.js'
        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"
            "angular-sanitize":
                version: ANGULAR_TAG
                files: "angular-sanitize.js"
            "showdown":
                version: '0.3.1'
                files: "compressed/showdown.js"

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures', 'vendors', 'templates', 'readme']

module.exports = config
