run_sequence = require 'run-sequence'
require("coffee-script/register")

# utilities
path = require('path')
fs = require('fs')
_ = require('lodash')

argv = require('minimist')(process.argv.slice(2))

# gulp plugins
ngClassify = require 'gulp-ng-classify'
gif = require 'gulp-if'
sourcemaps = require 'gulp-sourcemaps'
coffee = require 'gulp-coffee'
gutil = require 'gulp-util'
annotate = require 'gulp-ng-annotate'
concat = require 'gulp-concat'
cached = require 'gulp-cached'
karma = require 'gulp-karma'
remember = require 'gulp-remember'
uglify = require 'gulp-uglify'
jade = require 'gulp-jade'
rename = require 'gulp-rename'
bower = require 'gulp-bower-deps'
templateCache = require 'gulp-angular-templatecache'
lr = require 'gulp-livereload'
cssmin = require 'gulp-minify-css'
less = require 'gulp-less'
fixtures2js = require 'gulp-fixtures2js'
connect = require('connect')
serve_static = require("serve-static")

module.exports =  (gulp) ->
    # standard gulp is not cs friendly (cgulp is). you need to register coffeescript first to be able to load cs files


    # in prod mode, we uglify. in dev mode, we create sourcemaps
    # that should be the only difference, to minimize risk on difference between prod and dev builds
    prod = "prod" in argv._
    dev = "dev" in argv._

    # Load in the build config files
    config = require("./defaultconfig.coffee")
    buildConfig = require(path.join(process.cwd(), "guanlecoja", "config.coffee"))
    _.merge(config, buildConfig)

    bower = bower(config.bower)
    bower.installtask(gulp)

    # first thing, we remove the build dir
    # we do it synchronously to simplify things
    require('rimraf').sync(config.dir.build)

    error_handler = (e) ->
        error = gutil.colors.bold.red;
        if e.fileName?
            gutil.log(error("#{e.plugin}:#{e.name}: #{e.fileName} +#{e.lineNumber}"))
        else
            gutil.log(error("#{e.plugin}:#{e.name}"))
        gutil.log(error(e.message))
        gutil.beep()
        @.end()
        @emit("end")
        if not dev
            throw e

    # libs first, then app, then the rest
    script_sources = bower.deps.concat(config.files.app, config.files.scripts, config.files.templates)
    gulp.task 'scripts', ->
        gulp.src script_sources
            .pipe gif(dev, sourcemaps.init())
            .pipe cached('scripts')
            # coffee build
            .pipe(gif("*.coffee", ngClassify(config.ngclassify(config)).on('error', error_handler)))
            .pipe(gif("*.coffee", coffee().on('error', error_handler)))
            # jade build
            .pipe(gif("*.jade", jade().on('error', error_handler)))
            .pipe gif "*.html", rename (p) ->
                if config.name? or config.name is 'app'
                    p.dirname = path.join(config.name, "views")
                else
                    p.dirname = "views"
                p.basename = p.basename.replace(".tpl","")
                null
            .pipe remember('scripts')
            .pipe(gif("*.html", templateCache({module:config.name})))
            .pipe concat("scripts.js")
            # now everything is in js, do angular annotation, and minification
            .pipe gif(prod, annotate())
            .pipe gif(prod, uglify())
            .pipe gif(dev, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    gulp.task 'tests', ->
        src = bower.testdeps.concat(config.files.tests)
        gulp.src src
            .pipe cached('tests')
            .pipe gif(dev, sourcemaps.init())
            # coffee build
            .pipe(gif("*.coffee", ngClassify(config.ngclassify)))
            .pipe(gif("*.coffee", coffee().on('error', error_handler)))
            .pipe remember('tests')
            .pipe concat("tests.js")
            .pipe gif(dev, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build


    gulp.task 'generatedfixtures', config.generatedfixtures

    gulp.task 'fixtures', ->
        gulp.src config.files.fixtures, base: process.cwd()
            # fixtures
            .pipe rename dirname:""
            .pipe fixtures2js "fixtures.js",
                postProcessors:
                    "**/*.json": "json"
            .pipe gulp.dest config.dir.build

    gulp.task 'styles', ->
        gulp.src config.files.less
            .pipe cached('styles')
            .pipe less().on('error', error_handler)
            .pipe remember('styles')
            .pipe concat("styles.css")
            .pipe gif(prod, cssmin())
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    # just copy fonts and imgs to the output dir
    gulp.task 'fonts', ->
        gulp.src config.files.fonts
            .pipe rename dirname:""
            .pipe gulp.dest path.join(config.dir.build, "fonts")

    gulp.task 'imgs', ->
        gulp.src config.files.images
            .pipe rename dirname:""
            .pipe gulp.dest path.join(config.dir.build, "img")

    gulp.task 'index', ->
        gulp.src config.files.index
            .pipe jade().on('error', error_handler)
            .pipe gulp.dest config.dir.build

    # Run server.
    gulp.task 'server', ['index'], (next) ->
        if config.devserver?
            connect()
            .use(serve_static(config.dir.build))
            .listen(config.devserver.port, next)
        else
            next()
    gulp.task "watch", ->
        # karma own watch mode is used. no need to restart karma
        gulp.watch(script_sources, ["scripts"])
        gulp.watch(config.files.tests, ["tests"])
        gulp.watch(config.files.less, ["styles"])
        gulp.watch(config.files.index, ["index"])
        null

    gulp.task "karma", ->
        karmaconf =
            basePath: config.dir.build
            action: if dev then 'watch' else 'run'
        _.merge(karmaconf, config.karma)
        gulp.src ["scripts.js", 'generatedfixtures.js', "fixtures.js", "tests.js"]
            .pipe karma(karmaconf)

    gulp.task "default", (callback) ->
        run_sequence config.preparetasks, config.buildtasks, config.testtasks,
            callback

    gulp.task "dev", ['default', 'watch', "server"]

    # prod is a fake task, which enables minification
    gulp.task "prod", ['default']
