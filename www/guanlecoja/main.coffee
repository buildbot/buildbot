module.exports =  (gulp) ->
    # standard gulp is not cs friendly (cgulp is). you need to register coffeescript first to be able to load cs files

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
    templateCache = require 'gulp-angular-templatecache'
    lr = require 'gulp-livereload'
    cssmin = require 'gulp-minify-css'
    less = require 'gulp-less'
    fixtures2js = require 'gulp-fixtures2js'


    # in prod mode, we uglify. in dev mode, we create sourcemaps
    # that should be the only difference, to minimize risk on difference between prod and dev builds
    prod = "prod" in argv._
    dev = "dev" in argv._

    # Load in the build config files
    config = require("./defaultconfig.coffee")
    buildConfig = require(path.join(process.cwd(), "guanlecoja", "config.coffee"))
    _.merge(config, buildConfig)

    # first thing, we remove the build dir
    # we do it synchronously to simplify things
    require('rimraf').sync(config.dir.build)

    gulp.task 'scripts', ->
        # libs first, then app, then the rest
        src = config.files.library.js.concat(config.files.app, config.files.scripts, config.files.templates)
        gulp.src src
            .pipe cached('scripts')
            .pipe gif(dev, sourcemaps.init())
            # coffee build
            .pipe(gif("*.coffee", ngClassify())).on('error', gutil.log)
            .pipe(gif("*.coffee", coffee())).on('error', gutil.log)
            # jade build
            .pipe(gif("*.jade", jade())).on('error', gutil.log)
            .pipe gif "*.html", rename (p) ->
                p.dirname = "views"
                p.basename = p.basename.replace(".tpl","")
                null
            .pipe(gif("*.html", templateCache({module:"app"})))
            .pipe remember('scripts')
            .pipe concat("scripts.js")
            # now everything is in js, do angular annotation, and minification
            .pipe gif(prod, annotate())
            .pipe gif(prod, uglify())
            .pipe gif(dev, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    gulp.task 'tests', ->
        src = config.files.library.tests.concat(config.files.tests)
        gulp.src src
            .pipe cached('tests')
            .pipe gif(dev, sourcemaps.init())
            # coffee build
            .pipe(gif("*.coffee", ngClassify()))
            .pipe(gif("*.coffee", coffee())).on('error', gutil.log)
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
            .pipe less()
            .pipe remember('styles')
            .pipe concat("styles.css")
            .pipe gif(prod, cssmin())
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    # just copy fonts and imgs to the output dir
    gulp.task 'fonts', ->
        gulp.src config.files.fonts
            .pipe gulp.dest config.dir.build + "/fonts"

    gulp.task 'imgs', ->
        gulp.src config.files.images
            .pipe gulp.dest config.dir.build + "/img"

    gulp.task 'index', ->
        gulp.src config.files.index
            .pipe jade()
            .pipe gulp.dest config.dir.build


    gulp.task "watch", ->
        gulp.watch(config.files.scripts, ["scripts"])
        gulp.watch(config.files.tests, ["tests"])
        gulp.watch(config.files.less, ["styles"])


    gulp.task "default", ['scripts', 'styles', 'fonts', 'imgs', 'index', 'tests', 'generatedfixtures', 'fixtures'], ->
        karmaconf =
            basePath: config.dir.build
            action: if dev then 'watch' else 'run'
        _.merge(karmaconf, config.karma)
        gulp.src ["scripts.js", 'generatedfixtures.js', "fixtures.js", "tests.js"]
            .pipe karma(karmaconf)

    gulp.task "dev", ['default', 'watch']

    # prod is a fake task, which enables minification
    gulp.task "prod", ['default']
