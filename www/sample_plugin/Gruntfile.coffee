path = require 'path'

# Build configurations.
module.exports = (grunt) ->
    plugin_name =  "sample_plugin"
    changedFiles = {}
    firstPass = true
    grunt.event.on "watch", (action, filepath) ->
        firstPass = false
        changedFiles[filepath] = action
    # allows incremental build using watch
    hasChanged = (filepath) ->
        if firstPass
            return true
        if changedFiles.hasOwnProperty(filepath)
            delete changedFiles[filepath]
            return true
        return false

    grunt.initConfig
        # Deletes buildbot_www and temp directories.
        # The temp directory is used during the build process.
        # The buildbot_www directory contains the artifacts of the build.
        # These directories should be deleted before subsequent builds.
        # These directories are not committed to source control.
        clean:
            working:
                src: [
                    './buildbot_www/'
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

        # custom task that generates main.js (the require.js main file)
        # Angular is actually very nice with its dependancy injection system
        # basically, we just need angular is loaded first,  app second and run last
        # we should not be modifying this config when the app is growing
        requiregen:
            main:
                cwd: './.temp/'
                src: ['**/*.js','!libs/require.js']
                options:
                    order: [
                        plugin_name+'/libs/*'      # remaining libs before app
                        plugin_name+'/app'          # app needs libs
                        plugin_name+'/{routes,views,config,*/**}'  # remaining angularjs components
                    ]
                    define: true
                dest: '.temp/'+plugin_name+'/main.js'
        # Copies directories and files from one location to another.
        copy:
            # Copies the contents of the temp directory, except views, to the buildbot_www directory.
            # In 'dev' individual files are used.
            dev:
                files: [
                    cwd: './.temp/'+plugin_name+'/'
                    src: '**'
                    dest: './buildbot_www/'
                    expand: true
                ,
                    cwd: './.temp/'
                    src: 'img/**',
                    dest: './buildbot_www/'
                    expand: true
                ,
                    './buildbot_www/styles.css':'./.temp/styles/styles.css'
                ]
            # Copies img directory to temp.
            img:
                files: [
                    cwd: './src/'
                    src: 'img/**/*.*'
                    dest: './.temp/'
                    expand: true
                ]
            # Copies js files to the temp directory
            js:
                files: [
                    cwd: './src/scripts/'
                    src: '**/*.js'
                    dest: './.temp/'+plugin_name+'/'
                    expand: true
                ,
                    cwd: './src/'
                    src: 'scripts/**/*.js'
                    dest: './buildbot_www_test/'
                    expand: true
                ]
            # Copies coffee src files to the buildbot_ww directory
            src:
                files: [
                    cwd: './src/'
                    src: 'scripts/**/*.coffee'
                    dest: 'buildbot_www/src/'
                    expand: true
                    flatten: true
                ]
            # Copies select files from the temp directory to the buildbot_www directory.
            # In 'prod' minified files are used along with img and libs.
            # The buildbot_www artifacts contain only the files necessary to run the application.
            prod:
                files: [
                    cwd: './.temp/'
                    src: [
                        'img/**/*.*'
                    ]
                    dest: './buildbot_www/'
                    expand: true
                ,
                    './buildbot_www/main.js': '.temp/main.js'
                    './buildbot_www/styles.css': '.temp/styles/styles.min.css'
                ]
            # Task is run when the watched index.template file is modified.
            index:
                files: [
                    cwd: './.temp/'
                    src: 'index.html'
                    dest: './buildbot_www/'
                    expand: true
                ]
            # Task is run when a watched script is modified.
            scripts:
                files: [
                    cwd: "./.temp/#{plugin_name}/"
                    src: "**"
                    dest: './buildbot_www/'
                    expand: true
                ]
            # Task is run when a watched style is modified.
            styles:
                files:
                    './buildbot_www/styles.css':'./.temp/styles/styles.css'
            # Task is run when a watched view is modified.
            views:
                files: [
                    cwd: "./.temp/#{plugin_name}"
                    src: "views/**"
                    dest: './buildbot_www/'
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
        # This will produce a file with the following content.
        #
        # angular.module('app').run(['$templateCache', function ($templateCache) {
        #   $templateCache.put('/views/directives/tab.html', '<div class="tab-pane" ng-class="{active: selected}" ng-transclude></div>');
        #   $templateCache.put('/views/directives/tabs.html', '<div class="tabbable"> <ul class="nav nav-tabs"> <li ng-repeat="tab in tabs" ng-class="{active:tab.selected}"> <a href="http://localhost:3005/scripts/views.js" ng-click="select(tab)">{{tab.caption}}</a> </li> </ul> <div class="tab-content" ng-transclude></div> </div>');
        #   [...]
        # }]);
        #
        # This file is then included in the output automatically.  AngularJS will use it instead of going to the file system for the views, saving requests.  Notice that the view content is actually minified.  :)
        html2js:
            views:
                files: [
                    src: "./.temp/#{plugin_name}/views/**/*.html"
                    dest: "./.temp/#{plugin_name}/views.js"
                ]
                options:
                    base: './.temp/'

        # RequireJS optimizer configuration for both scripts and styles.
        # This configuration is only used in the 'prod' build.
        # The optimizer will scan the main file, walk the dependency tree, and write the output in dependent sequence to a single file.
        # The main file is used only to establish the proper loading sequence.
        requirejs:
            scripts:
                options:
                    baseUrl: './.temp/'
                    findNestedDependencies: true
                    logLevel: 2
                    mainConfigFile: './.temp/'+plugin_name+'/main.js'
                    name: plugin_name+'/main'
                    # Exclude main from the final output to avoid the dependency on RequireJS at runtime.
                    onBuildWrite: (moduleName, path, contents) ->
                        modulesToExclude = [plugin_name+'/main']
                        shouldExcludeModule = modulesToExclude.indexOf(moduleName) >= 0

                        return '' if shouldExcludeModule

                        contents
                    optimize: 'uglify'
                    out: './.temp/main.js'
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
                    dest: "./.temp/#{plugin_name}/views/"
                    cwd: "./src/views"
                    ext: ".html"
                    expand: true
                ]

        # Runs unit tests using karma
        karma:
            options:
                colors: true
                keepalive: true
                autoWatch: false
                background: true
                reporters: ['progress']
                frameworks: ['jasmine', 'requirejs'],
                files: [
                    './buildbot_www/scripts/test/main.js'
                    {pattern: 'buildbot_www/scripts/**/*.js', included: false},
                    {pattern: 'buildbot_www/scripts/**/*.js.map', included: false},
                ]
                singleRun: false
            dev:
                options:
                    browsers: (grunt.option('browsers') or 'Chrome,Firefox,PhantomJS').split(",")
            ci:
                options:
                    background: false
                    autoWatch: false
                    browsers: ['PhantomJS']
                    singleRun: true

        # Sets up file watchers and runs tasks when watched files are changed.
        watch:
            scripts:
                files: ['./src/scripts/**','./test/scripts/**']
                tasks: [
                    'coffee:scripts'
                    'coffee:testscripts'
                    'copy:js'
                    'copy:scripts'
                    'copy:src'
                    'karma:dev:run'
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
                files: './buildbot_www/**'
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


    # https://github.com/karlgoldstein/grunt-html2js
    grunt.loadNpmTasks 'grunt-html2js'
    # https://github.com/Dignifiedquire/grunt-karma
    grunt.loadNpmTasks 'grunt-karma'
    # https://github.com/tardyp/grunt-requiregen
    grunt.loadNpmTasks 'grunt-requiregen'


    # Compiles the app with non-optimized build settings and places the build artifacts in the buildbot_www directory.
    # Enter the following command at the command line to execute this build task:
    # grunt
    grunt.registerTask 'default', [
        'clean:working'
        'coffee:scripts'
        'copy:js'
        'requiregen:main'
        'less'
        'jade:views'
        'copy:img'
        'copy:dev'
        'copy:src'
    ]

    # Compiles the app with non-optimized build settings, places the build artifacts in the buildbot_www directory, and watches for file changes.
    # Enter the following command at the command line to execute this build task:
    # grunt dev
    grunt.registerTask 'dev', [
        'default'
        'karma:dev'
        'watch',
    ]
    # Compiles the app with non-optimized build settings, places the build artifacts in the buildbot_www directory, and runs unit tests.
    # Enter the following command at the command line to execute this build task:
    # grunt ci
    grunt.registerTask 'ci', [
        'default'
        'karma:ci'
    ]


    # Compiles the app with optimized build settings and places the build artifacts in the buildbot_www directory.
    # Enter the following command at the command line to execute this build task:
    # grunt prod
    grunt.registerTask 'prod', [
        'clean:working'
        'coffee:scripts'
        'copy:js'
        'requiregen:main'
        'copy:img'
        'less'
        'jade:views'
        'imagemin'
        'html2js'
        'requirejs'
        'copy:prod'
    ]