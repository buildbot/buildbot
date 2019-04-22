require "./vendors"
vendors = global.vendors

# Stuff that we can't import via browserify

# runsequence needs to be at the same level as gulp
# ng-classify is in coffee, so it does not work with browserify out of the box
ngClassify = require 'gulp-ng-classify'
path = require 'path'

# karma does not work with browserify
karma = require 'karma'

# sass uses native code, and cannot be browserified
sass = require('gulp-sass')

# utilities
path = vendors.path
fs = vendors.fs
_ = vendors._

argv = vendors.minimist(process.argv.slice(2))

# gulp plugins

run_sequence = vendors.run_sequence
gif = vendors.gif
babel = vendors.babel
sourcemaps = vendors.sourcemaps
coffee = vendors.coffee
gutil = vendors.gutil
annotate = vendors.annotate
concat = vendors.concat
cached = vendors.cached
remember = vendors.remember
uglify = vendors.uglify
jade = vendors.jade
wrap = vendors.wrap
rename = vendors.rename
bower = vendors.bower
templateCache = vendors.templateCache
lr = vendors.lr
cssmin = vendors.cssmin
less = vendors.less
fixtures2js = vendors.fixtures2js
gulp_help = vendors.gulp_help
lazypipe = vendors.lazypipe

# dependencies for webserver
connect = vendors.connect
serveStatic = vendors.static

# this cannot be browserified, because browserify's require does not support registering
require "coffee-script/register"

module.exports =  (gulp) ->
    run_sequence = run_sequence.use(gulp)
    # standard gulp is not cs friendly (cgulp is). you need to register coffeescript first to be able to load cs files
    gulp = gulp_help gulp, afterPrintCallback: (tasks) ->
        console.log(gutil.colors.underline("Options:"))
        console.log(gutil.colors.cyan("  --coverage") + " Runs the test with coverage reports")
        console.log(gutil.colors.cyan("  --notests") + "  Skip running the tests")
        console.log("")

    # in prod mode, we uglify. in dev mode, we create sourcemaps
    # that should be the only difference, to minimize risk on difference between prod and dev builds
    prod = "prod" in argv._
    dev = "dev" in argv._
    coverage = argv.coverage
    notests = argv.notests

    # Load in the build config files
    config = require("./defaultconfig.coffee")
    buildConfigPath = path.join(process.cwd(), "guanlecoja", "config.js")
    if not fs.existsSync(buildConfigPath)
        buildConfigPath = path.join(process.cwd(), "guanlecoja", "config.coffee")

    buildConfig = require(buildConfigPath)
    _.merge(config, buildConfig)

    # _.merge does not play well with lists, we just take the overridden version
    if buildConfig.karma?.files?
        config.karma.files = buildConfig.karma.files
    if buildConfig.buildtasks?
        config.buildtasks = buildConfig.buildtasks

    bower = bower(config.bower)
    bower.installtask(gulp)

    # first thing, we remove the build dir
    # we do it synchronously to simplify things
    vendors.rimraf.sync(config.dir.build)

    if coverage
        vendors.rimraf.sync(config.dir.coverage)

    if notests
        config.testtasks = ["notests"]

    catch_errors = (s) ->
        s.on "error", (e) ->
            error = gutil.colors.bold.red
            if e.filename? and e.location?
                gutil.log(error("#{e.plugin}:#{e.name}: #{e.filename} +#{e.location.first_line}"))
            else if e.fileName?
                gutil.log(error("#{e.plugin}:#{e.name}: #{e.fileName} +#{e.lineNumber}"))
            else
                gutil.log(error("#{e.plugin}:#{e.name}"))
            gutil.log(error(e.message))
            gutil.beep()
            s.end()
            s.emit("end")
            if not dev
                throw "stopping because of previous error"
            return null
        s

    # if coverage, we need to put vendors and templates apart
    if coverage
        config.vendors_apart = true
        config.templates_apart = true

    script_sources = config.files.app.concat(config.files.scripts)

    unless config.vendors_apart
        # libs first, then app, then the rest
        script_sources = bower.deps.concat(script_sources)

    unless config.templates_apart
        script_sources = script_sources.concat(config.files.templates)

    jadeConcat = lazypipe()
    .pipe(concat, config.output_templates)
    .pipe(wrap, "window.#{config.templates_global}={}; <%= contents %>")

    if config.templates_as_js
        jadeCompile = lazypipe()
        .pipe jade, client:true
        .pipe(rename, extname: "") # remove two extensions ".tpl.js"
        .pipe(rename, extname: "")
        .pipe(wrap, "window.#{config.templates_global}['<%= file.relative %>'] = <%= contents %>;")
        .pipe(rename, extname: ".jjs")
    else
        jadeCompile = lazypipe()
        .pipe jade
        .pipe rename, (p) ->
            if config.name? and config.name isnt 'app'
                p.dirname = path.join(config.name, "views")
            else
                p.dirname = "views"
            p.basename = p.basename.replace(".tpl","")

    coffeeCompile = lazypipe()
    .pipe ngClassify, config.ngclassify(config)
    .pipe coffee

    # main scripts task.
    # if coffee_coverage, we only pre-process ngclassify, and karma will do the rest
    # in other cases, we have a more complex setup, if order to enable joining all
    # the sources (vendors, scripts, and templates)
    gulp.task 'scripts', false, ->
        if coverage and config.coffee_coverage
            return gulp.src script_sources
                .pipe(catch_errors(gif("*.coffee", ngClassify(config.ngclassify(config)))))
                .pipe gulp.dest path.join(config.dir.coverage, config.dir.src)

        gulp.src script_sources
            .pipe gif(dev or config.sourcemaps, sourcemaps.init())
            .pipe cached('scripts')
            # babel build
            .pipe(catch_errors(gif("*.js", babel({
                presets: [
                    [   '@babel/preset-env',
                        "targets": {
                           "chrome": "56",
                           "firefox": "52",
                           "edge": "13",
                           "safari": "10"
                        },
                        "modules": false
                    ]
                ]
            }))))
            # coffee build
            .pipe(catch_errors(gif("*.coffee", coffeeCompile().pipe(gif(prod, annotate())))))
            # jade build
            .pipe(catch_errors(gif("*.jade", jadeCompile())))
            .pipe(catch_errors(gif("*.pug", jadeCompile())))
            .pipe remember('scripts')
            .pipe(gif("*.html", templateCache({module:config.name})))
            .pipe(catch_errors(gif("*.jjs", jadeConcat())))
            .pipe concat(config.output_scripts)
            # now everything is in js, do minification
            .pipe gif(prod, uglify())
            .pipe gif(dev or config.sourcemaps, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    # concat vendors apart
    gulp.task 'vendors', false, ->
        unless config.vendors_apart and bower.deps.length > 0
            return
        gulp.src bower.deps
            .pipe gif(dev or config.sourcemaps, sourcemaps.init())
            .pipe(catch_errors(gif("*.js", babel({
                presets: [
                    [   '@babel/preset-env',
                        "targets": {
                           "chrome": "56",
                           "firefox": "52",
                           "edge": "13",
                           "safari": "10"
                        },
                        "modules": false
                    ]
                ]
            }))))
            .pipe concat("vendors.js")
            # now everything is in js, do angular annotation, and minification
            .pipe gif(prod, uglify())
            .pipe gif(dev or config.sourcemaps, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    # build and concat templates apart
    gulp.task 'templates', false, ->
        unless config.templates_apart
            return
        gulp.src config.files.templates
            # jade build
            .pipe(catch_errors(gif("*.jade", jade())))
            .pipe(catch_errors(gif("*.pug", jade())))
            .pipe gif "*.html", rename (p) ->
                if config.name? and config.name isnt 'app'
                    p.dirname = path.join(config.name, "views")
                else
                    p.dirname = "views"
                p.basename = p.basename.replace(".tpl","")
                null
            .pipe(gif("*.html", templateCache({module:config.name})))
            .pipe concat(config.output_templates)
            .pipe gulp.dest config.dir.build

    # the tests files produce another file
    gulp.task 'tests', false, ->
        src = bower.testdeps.concat(config.files.tests)
        gulp.src src
            .pipe cached('tests')
            .pipe gif(dev, sourcemaps.init())
            # babel build
            .pipe(catch_errors(gif("*.js", babel({
                presets: [
                    [   '@babel/preset-env',
                        "targets": {
                           "chrome": "56",
                           "firefox": "52",
                           "edge": "13",
                           "safari": "10"
                        },
                        "modules": false
                    ]
                ]
            }))))
            # coffee build
            .pipe(catch_errors(gif("*.coffee", ngClassify(config.ngclassify))))
            .pipe(catch_errors(gif("*.coffee", coffee())))
            .pipe remember('tests')
            .pipe concat(config.output_tests)
            .pipe gif(dev, sourcemaps.write("."))
            .pipe gulp.dest config.dir.build


    # a customizable task that generates fixtures from external tool
    gulp.task 'generatedfixtures', false, config.generatedfixtures

    # a task to compile json fixtures into constants that sits on window.FIXTURES
    gulp.task 'fixtures', false, ->
        gulp.src config.files.fixtures, base: process.cwd()
            # fixtures
            .pipe rename dirname:""
            .pipe fixtures2js "fixtures.js",
                postProcessors:
                    "**/*.json": "json"
            .pipe gulp.dest config.dir.build

    # a task to compile less files
    gulp.task 'styles', false, ->
        gulp.src config.files.less.concat(config.files.sass)
            .pipe cached('styles')
            .pipe(catch_errors(gif("*.less", less())))
            .pipe(catch_errors(gif("*.scss", sass({includePaths: [config.bower.directory]}))))
            .pipe remember('styles')
            .pipe concat(config.output_styles)
            .pipe gif(prod, cssmin())
            .pipe gulp.dest config.dir.build
            .pipe gif(dev, lr())

    # just copy fonts and imgs to the output dir
    gulp.task 'fonts', false, ->
        gulp.src config.files.fonts
            .pipe rename dirname:""
            .pipe gulp.dest path.join(config.dir.build, "fonts")

    gulp.task 'imgs', false, ->
        gulp.src config.files.images
            .pipe rename dirname:""
            .pipe gulp.dest path.join(config.dir.build, "img")

    # index.jade build
    gulp.task 'index', false, ->
        gulp.src config.files.index
            .pipe catch_errors(jade())
            .pipe gulp.dest config.dir.build

    # Run server.
    gulp.task 'server', false, ['index'], (next) ->
        if config.devserver?
            app = connect()
            app.use(serveStatic(config.dir.build))
            app.listen(config.devserver.port)
        else
            next()

    gulp.task "watch", false, ->
        lr.listen(livereload:path.join(__dirname,"livereload.js"))
        # karma own watch mode is used. no need to restart karma
        gulp.watch(script_sources, ["scripts"])
        gulp.watch(config.files.templates, ["templates"])
        gulp.watch(config.files.tests, ["tests"])
        gulp.watch(config.files.less, ["styles"])
        gulp.watch(config.files.sass, ["styles"])
        gulp.watch(config.files.index, ["index"])
        null

    # karma configuration, we build a lot of the config file automatically
    gulp.task "karma", false, (done) ->
        karmaconf =
            basePath: config.dir.build
        if not dev
            karmaconf.singleRun = true
        _.merge(karmaconf, config.karma)
        if (process.env.CI)
            karmaconf.browsers = karmaconf.browsers_ci

        if config.vendors_apart
            karmaconf.files = [config.output_vendors].concat(config.karma.files)

        if config.templates_apart
            karmaconf.files = karmaconf.files.concat([config.output_templates])
        if coverage
            karmaconf.reporters.push("coverage")
            karmaconf.preprocessors = {
                "**/#{config.output_scripts}": ['sourcemap']
                "**/#{config.output_tests}": ['sourcemap']
                "**/#{config.dir.src}/**/*.coffee": ['coffee', 'coverage']
                "**/#{config.dir.src}/**/*.js": ['coverage']
            }
            for r in karmaconf.coverageReporter.reporters
                if r.dir == "coverage"
                    r.dir = config.dir.coverage
            karmaconf.basePath = "."
            scripts_index = karmaconf.files.indexOf(config.output_scripts)
            karmaconf.files = karmaconf.files.map (p) -> path.join(config.dir.build, p)

            if config.coffee_coverage
                # insert the pre-classified files inside the karma config file list
                # (after vendors.js)
                classified = script_sources.map (p) ->
                    path.join("coverage", p)
                karmaconf.files.splice.apply(karmaconf.files, [scripts_index, 1].concat(classified))
        mydone = (code) ->
            done()
            # need process.exit to avoid need for a double ctrl-c
            # karma watch is overriding ctrl-c, then the gulp watch does not see it
            if dev
                process.exit(code)
        server = new karma.Server(karmaconf, mydone)
        server.start()
        return null

    gulp.task "notests", false, ->
        null

    defaultHelp = "Build and test the code once, without minification"
    if argv.help or argv.h
        # we replace default task when help is requested
        gulp.task "default", defaultHelp, ['help'], ->
    else
        gulp.task "default", defaultHelp, (callback) ->
            run_sequence config.preparetasks, config.buildtasks, config.testtasks,
                callback
    devHelp = "Run needed tasks for development:
        build,
        tests,
        watch and rebuild. This task only ends when you hit CTRL-C!"
    if config.devserver
        devHelp += "\nAlso runs the dev server"

    gulp.task "dev", devHelp, ['default', 'watch', "server"]
    # prod is a fake task, which enables minification
    gulp.task "prod", "Run production build (minified)", ['default']
