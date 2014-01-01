path = require 'path'

# Build configurations.
module.exports = (grunt) ->
    project_name = "buildbot_www"

    # allows incremental build using watch
    # follow https://github.com/gruntjs/grunt-contrib-watch/issues/156
    # for a better solution :-/
    changedFiles = {}
    firstPass = true
    grunt.event.on "watch", (action, filepath) ->
        firstPass = false
        changedFiles[filepath] = action
    hasChanged = (filepath) ->
        if firstPass
            return true
        if changedFiles.hasOwnProperty(filepath)
            setTimeout ->
                delete changedFiles[filepath]
            , 10000
            return true
        return false

    grunt.initConfig
        # Deletes #{project_name} and temp directories.
        # The temp directory is used during the build process.
        # The #{project_name} directory contains the artifacts of the build.
        # These directories should be deleted before subsequent builds.
        # These directories are not committed to source control.
        clean:
            working:
                src: [
                    "./#{project_name}/"
                    './.temp/'
                ]

        # Compile CoffeeScript (.coffee) files to JavaScript (.js).
        coffee:
            scripts:
                files: [
                    cwd: './src/'
                    src: 'scripts/**/*.coffee'
                    dest: './.temp/'
                    expand: true
                    ext: '.js'
                    filter: hasChanged
                ]
            testscripts:
                files: [
                    cwd: './test/scripts/'
                    src: '**/*.coffee'
                    dest: './.temp/scripts/test/'
                    expand: true
                    ext: '.js'
                    filter: hasChanged
                ]
            options:
                sourceMap: true
                sourceRoot : '/src'

        # CoffeeScript lint. Enforce basic coding style rules
        coffeelint:
            scripts:
                files: [
                    src: 'src/scripts/**/*.coffee'
                    filter: hasChanged
                ,
                    src: 'test/scripts/**/*.coffee'
                    filter: hasChanged
                ]
                options:
                    no_tabs:
                        level: "error"
                    no_trailing_whitespace:
                        level: "error"
                        allowed_in_comments: false
                    max_line_length:
                        value: 100
                        level: "error"
                    camel_case_classes:
                        level: "error"
                    indentation:
                        value: 4
                        level: "error"
                    no_implicit_braces:
                        level: "ignore"
                    no_trailing_semicolons:
                        level: "error"
                    no_plusplus:
                        level: "ignore"
                    no_throwing_strings:
                        level: "error"
                    # at some point we probably need to enable this rule
                    # for the moment, We dont have the proper design patterns
                    # to resolve those issues
                    cyclomatic_complexity:
                        value: 10
                        level: "ignore"
                    no_backticks:
                        level: "error"
                    line_endings:
                        level: "error"
                        value: "unix"
                    no_implicit_parens:
                        level: "ignore"
                    empty_constructor_needs_parens:
                        level: "error"
                    non_empty_constructor_needs_parens:
                        level: "error"
                    no_empty_param_list:
                        level: "error"
                    space_operators:
                        level: "error"
                    duplicate_key:
                        level: "error"
                    newlines_after_classes:
                        value: 2
                        level: "error"
                    no_stand_alone_at:
                        level: "error"
                    arrow_spacing:
                        level: "error"
                    coffeescript_error:
                        level: "error"
        concat:
            # concat bower.json files into config.js, to display deps in the UI
            # we declare a constant in the 'app' module
            bower_configs:
                src: ['bower_components/**/bower.json']
                dest: '.temp/scripts/config.js'
                options:
                    separator:','
                    banner: 'angular.module("app").constant("bower_configs", ['
                    footer: '])'

        # custom task that generates main.js (the require.js main file)
        # Angular is actually very nice with its dependancy injection system
        # basically, we just need angular is loaded first,  app second and run last
        # we should not be modifying this config when the app is growing
        requiregen:
            main:
                cwd: './.temp/scripts/'
                # require json2 and html5shiv are loaded in the html file
                src: ['**/*.js','!libs/require.js', '!libs/json2.js',
                      '!libs/html5shiv-printshiv.js']
                options:
                    order: [
                    # order is a list of regular expression matching
                    # modules, requiregen will generate the correct shim
                    # to load modules in this order
                    # if a module has been loaded in previous layers, it wont be loaded again
                    # so that you can use global regular expression in the end
                        'libs/jquery'
                        'libs/angular'     # angular needs jquery before or will use internal jqlite
                        'libs/*'           # remaining libs before app
                        'test/libs/*'      # test libs in dev mode
                        'test/dataspec'    # test mocks in dev mode
                        'test/mocks/*'     # test mocks in dev mode
                        'app'              # app needs libs
                        'routes'           # default routes first
                        '{views,config,*/**}'    # remaining angularjs components
                        'run'     # run has to be in the end, because it is triggering
                                  # angular's own DI
                    ]
                dest: '.temp/scripts/main.js'
        # Copies directories and files from one location to another.
        copy:
            # Copies the contents of the temp directory, except views,
            # to the #{project_name} directory.
            # In 'dev' individual files are used.
            dev:
                files: [
                    cwd: './.temp/'
                    src: '**'
                    dest: "./#{project_name}/"
                    expand: true
                ]
            # Copies img directory to temp.
            img:
                files: [
                    cwd: './src/'
                    src: 'img/**/*.*'
                    dest: './.temp/'
                    expand: true
                ]
            # Copies font directory to temp.
            font:
                files: [
                    cwd: './src/'
                    src: 'fonts/**/*.*'
                    dest: './.temp/'
                    expand: true
                ]
            # Copies js files to the temp directory
            js:
                files: [
                    cwd: './src/'
                    src: 'scripts/**/*.js'
                    dest: './.temp/'
                    expand: true
                ]
            # Copies js files to the temp directory
            testjs:
                files: [
                    cwd: './test/scripts/'
                    src: '**/*.js'
                    dest: './.temp/scripts/test'
                    expand: true
                ]
            # Copies coffee src files to the #{project_name} directory
            src:
                files: [
                    cwd: './'
                    src: '*/scripts/**/*.coffee'
                    dest: "#{project_name}/src/"
                    expand: true
                    flatten: true
                ]
            # Copies select files from the temp directory to the #{project_name} directory.
            # In 'prod' minified files are used along with img and libs.
            # The #{project_name} artifacts contain only the files necessary to run the application.
            prod:
                files: [
                    cwd: './.temp/'
                    src: [
                        'img/**/*.*'
                        'fonts/**/*.*'
                        'scripts/libs/html5shiv-printshiv.js'
                        'scripts/libs/json2.js'

                        'scripts/scripts.min.js'
                        'styles/styles.min.css'
                        'index.html'
                    ]
                    dest: "./#{project_name}/"
                    expand: true
                ,
                    dest: "./#{project_name}/require.js"
                    src: './.temp/scripts/libs/require.js'
                ]
            # Task is run when the watched index.template file is modified.
            index:
                files: [
                    cwd: './.temp/'
                    src: 'index.html'
                    dest: "./#{project_name}/"
                    expand: true
                ]
            # Task is run when a watched script is modified.
            scripts:
                files: [
                    cwd: './.temp/'
                    src: 'scripts/**'
                    dest: "./#{project_name}/"
                    expand: true
                ]
            # Task is run when a watched style is modified.
            styles:
                files: [
                    cwd: './.temp/'
                    src: 'styles/**'
                    dest: "./#{project_name}/"
                    expand: true
                ]
            # Task is run when a watched view is modified.
            views:
                files: [
                    cwd: './.temp/'
                    src: 'views/**'
                    dest: "./#{project_name}/"
                    expand: true
                ]

        # Compresses png files
        imagemin:
            img:
                files: [
                    cwd: './src/'
                    src: 'img/**/*.png'
                    dest: './.temp/'
                    expand: true
                ]
                options:
                    optimizationLevel: 7

        # Compile LESS (.less) files to CSS (.css).
        less:
            styles:
                files:
                    './.temp/styles/styles.css': './src/styles/styles.less'

        # Gathers all views and creates a file to push views directly into the $templateCache
        html2js:
            views:
                files: './.temp/scripts/views.js':'./.temp/views/**/*.html'
                options:
                    base: './.temp/'
        # RequireJS optimizer configuration for both scripts and styles.
        # This configuration is only used in the 'prod' build.
        # The optimizer will scan the main file, walk the dependency tree, and write
        # the output in dependent sequence to a single file.
        # The main file is used only to establish the proper loading sequence.
        requirejs:
            scripts:
                options:
                    baseUrl: './.temp/scripts/'
                    findNestedDependencies: true
                    logLevel: 0
                    mainConfigFile: './.temp/scripts/main.js'
                    name: 'main'
                    # Exclude main from the final output to avoid the dependency on
                    # RequireJS at runtime.
                    onBuildWrite: (moduleName, path, contents) ->
                        modulesToExclude = ['main']
                        shouldExcludeModule = modulesToExclude.indexOf(moduleName) >= 0

                        return '' if shouldExcludeModule

                        contents
                    optimize: 'uglify2'
                    out: './.temp/scripts/scripts.min.js'
                    preserveLicenseComments: false
                    skipModuleInsertion: true
                    uglify:
                        # Let uglifier replace variables to further reduce file size.
                        no_mangle: false
            styles:
                options:
                    baseUrl: './.temp/styles/'
                    cssIn: './.temp/styles/styles.css'
                    logLevel: 0
                    optimizeCss: 'standard'
                    out: './.temp/styles/styles.min.css'

        # Compile jade files (.jade) to HTML (.html).
        #
        jade:
            views:
                files:[
                    src:'**/*.jade'
                    dest: './.temp/views/'
                    cwd: './src/views'
                    ext: ".html"
                    expand: true
                ]
            dev:
                files:
                    './.temp/index.html': './src/index.jade'
                options:
                    data:
                        timestamp: "<%= grunt.template.today() %>"
                        environment: 'dev'
            prod:
                files: '<%= jade.dev.files %>'
                options:
                    data:
                        timestamp: "<%= grunt.template.today() %>"
                        environment: 'prod'

        # Runs unit tests using karma
        karma:
            options:
                colors: true
                keepalive: true
                autoWatch: false
                background: false
                singleRun: true
                reporters: ['progress']
                frameworks: ['jasmine', 'requirejs'],
                browsers: ['PhantomJS']
                preprocessors:
                    '**/*.coffee': ['coffee']
                ,
                files: [
                    "#{project_name}/scripts/test/main.js",
                    {pattern: "#{project_name}/scripts/**/*.js", included: false},
                    {pattern: "#{project_name}/scripts/**/*.js.map", included: false},
                ]
            dev:
                options: # choose from Chrome,Firefox,PhantomJS
                    browsers: (grunt.option('browsers') or 'PhantomJS').split(",")
                    background: true
                    singleRun: false
            ci:
                options:
                    singleRun: true
            prod:
                options:
                    files: [
                        './src/scripts/libs/jquery.js'
                        './src/scripts/libs/angular.js'
                        './test/scripts/libs/angular-mocks.js'
                        '.temp/scripts/test/dataspec.js'
                        './test/scripts/*/**.coffee'
                        "./#{project_name}/scripts/scripts.min.js"
                    ]

        # Sets up file watchers and runs tasks when watched files are changed.
        watch:
            index:
                files: './src/index.jade'
                tasks: [
                    'jade:dev'
                    'copy:index'
                ]
            scripts:
                files: ['./src/scripts/**', './test/scripts/**']
                tasks: [
                    'coffee:scripts'
                    'coffee:testscripts'
                    'copy:js'
                    'copy:scripts'
                    'copy:src'
                    'karma:dev'
                    'coffeelint:scripts'
                ]
                options:
                    spawn: false,
            styles:
                files: './src/styles/**/*.less'
                tasks: [
                    'less'
                    'copy:styles'
                ]
            views:
                files: './src/views/**/*.jade'
                tasks: [
                    'jade:views'
                    'copy:views'
                ]
            livereload:
                files: "./#{project_name}/**"
                options: {livereload: true}

    # Register grunt tasks supplied by grunt-contrib-*.
    # Referenced in package.json.
    # https://github.com/gruntjs/grunt-contrib
    grunt.loadNpmTasks 'grunt-contrib-clean'
    grunt.loadNpmTasks 'grunt-contrib-coffee'
    grunt.loadNpmTasks 'grunt-contrib-copy'
    grunt.loadNpmTasks 'grunt-contrib-imagemin'
    grunt.loadNpmTasks 'grunt-contrib-less'
    grunt.loadNpmTasks 'grunt-contrib-jade'
    grunt.loadNpmTasks 'grunt-contrib-livereload'
    grunt.loadNpmTasks 'grunt-contrib-requirejs'
    grunt.loadNpmTasks 'grunt-contrib-watch'
    grunt.loadNpmTasks 'grunt-contrib-concat'


    # Register grunt tasks supplied by grunt-html2js.
    # Referenced in package.json.
    # https://github.com/karlgoldstein/grunt-html2js
    grunt.loadNpmTasks 'grunt-html2js'

    # Register grunt tasks supplied by grunt-karma.
    # Referenced in package.json.
    # https://github.com/Dignifiedquire/grunt-karma
    grunt.loadNpmTasks 'grunt-karma'
    grunt.loadNpmTasks 'grunt-requiregen'

    # Register grunt tasks supplied by grunt-coffeelint.
    grunt.loadNpmTasks 'grunt-coffeelint'

    grunt.registerTask 'dataspec', ->
        done = @async()
        grunt.util.spawn
            cmd: "buildbot"
            args: "dataspec -o .temp/scripts/test/dataspec.js -g dataspec".split(" ")
        , (error, result, code) ->
            grunt.log.write result.toString()
            done(!error)


    # Compiles the app with non-optimized build settings and places the build artifacts
    # in the #{project_name} directory.
    # Enter the following command at the command line to execute this build task:
    # grunt
    grunt.registerTask 'default', [
        'clean:working'
        'concat:bower_configs'
        'dataspec'
        'coffee'
        'copy:js'
        'copy:testjs'
        'requiregen:main'
        'less'
        'jade:views'
        'copy:img'
        'copy:font'
        'jade:dev'
        'copy:dev'
        'copy:src'
    ]

    # Compiles the app with non-optimized build settings, places the build artifacts
    # in the #{project_name} directory, and watches for file changes.
    # Enter the following command at the command line to execute this build task:
    # grunt dev
    grunt.registerTask 'dev', [
        'karma:dev'
        'default'
        'karma:dev:run'
        'watch',
    ]

    # steps needed for ci. compile in dev mode and in prod, run tests for each
    # Enter the following command at the command line to execute this build task:
    # grunt ci
    grunt.registerTask 'ci', [
        'default'
        'coffeelint'
        'karma:ci'
        'prod'
        'dataspec'
        'karma:prod'
    ]
    # Compiles the app with optimized build settings and places the build artifacts
    # in the #{project_name} directory.
    # Enter the following command at the command line to execute this build task:
    # grunt prod
    grunt.registerTask 'prod', [
        'clean:working'
        'concat:bower_configs'
        'coffee:scripts'
        'copy:js'
        'requiregen:main'
        'copy:font'
        'copy:img'
        'less'
        'jade:views'
        'imagemin'
        'html2js'
        'requirejs'
        'jade:prod'
        'copy:prod'
    ]
    grunt.file.write("coffeelint.json", JSON.stringify(grunt.config("coffeelint.scripts.options")))
