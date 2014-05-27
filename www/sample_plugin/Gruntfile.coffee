path = require 'path'

# Build configurations.
module.exports = (grunt) ->

    # Load grunt tasks automatically
    require('load-grunt-tasks')(grunt)

    grunt.initConfig

        plugin:
            name: 'sample_plugin'

        # Deletes buildbot_www and temp directories.
        # The temp directory is used during the build process.
        # The buildbot_www directory contains the artifacts of the build.
        # These directories should be deleted before subsequent builds.
        # These directories are not committed to source control.
        clean:
            working:
                src: [
                    '.temp'
                    'buildbot_www'
                ]
            scripts_temp:
                src: [
                    '.temp/<%= plugin.name %>/scripts-temp'
                ]

        # Compile CoffeeScript (.coffee) files to JavaScript (.js).
        coffee:
            dev:
                options:
                    sourceMap: true
                files: [
                    cwd: 'src/scripts'
                    src: '{,*/}*.coffee'
                    dest: '.temp/<%= plugin.name %>/scripts'
                    expand: true
                    ext: '.js'
                ]
            prod:
                files: [
                    cwd: 'src/scripts'
                    src: '{,*/}*.coffee'
                    dest: '.temp/<%= plugin.name %>/scripts-temp'
                    expand: true
                    ext: '.js'
                ]
            test:
                files: [
                    cwd: 'test/scripts'
                    src: '{,*/}*.coffee'
                    dest: '.temp/<%= plugin.name %>/scripts/test'
                    expand: true
                    ext: '.js'
                ]

        # Compile LESS (.less) files to CSS (.css).
        less:
            dev:
                files: [
                    src: 'src/styles/styles.less'
                    dest: '.temp/<%= plugin.name %>/styles/styles.css'
                ]
            prod:
                options:
                    # optimize css
                    cleancss: true
                files: [
                    src: 'src/styles/styles.less'
                    dest: '.temp/<%= plugin.name %>/styles/styles.css'
                ]

        # Compile Jade files (.jade) to HTML (.html).
        jade:
            compile:
                options:
                    pretty: true
                files: [
                    cwd: 'src/views'
                    src:'**/*.jade'
                    dest: '.temp/<%= plugin.name %>/views'
                    ext: '.html'
                    expand: true
                ]

        # Gathers all views and creates a file to push views directly into the $templateCache
        # This will produce a file with the following content:
        # angular.module('app').run(["$templateCache", function($templateCache) {
        #   $templateCache.put("home.html",
        #   // contents for home.html ...
        #   );
        #   }]);
        # Then, when you use ng-include or templateUrl with $routeProvider, the template is already loaded without an extra AJAX request!
        ngtemplates:
            app:
                cwd: '.temp'
                src: '<%= plugin.name %>/views/**/*.html'
                dest: '.temp/<%= plugin.name %>/scripts/views.js'

        # Compresses images
        imagemin:
            img:
                options:
                    optimizationLevel: 7
                files: [
                    cwd: 'src'
                    src: ['img/**/*.{png,jpg,gif}']
                    dest: '.temp/<%= plugin.name %>'
                    expand: true
                ]

        # Custom task that generates main.js (the require.js main file)
        # Angular is actually very nice with its dependancy injection system
        # basically, we just need angular is loaded first,  app second and run last
        # we should not be modifying this config when the app is growing
        requiregen:
            main:
                cwd: '.temp'
                src: ['**/*.js']
                options:
                    order: [
                        '<%= plugin.name %>/scripts/libs/*'                         # remaining libs before app
                        '<%= plugin.name %>/scripts/app'                            # app needs libs
                        '<%= plugin.name %>/scripts/{routes,views,config,*/**}'     # remaining angularjs components
                    ]
                    define: true
                dest: '.temp/<%= plugin.name %>/main.js'

        # Copies directories and files from one location to another.
        copy:
            # Copies bower components to the libs directory
            bower:
                files: [
                    cwd: 'bower_components'
                    src: ['{,*/}*.js', '!{,*/}*.min.js', '!{,*/}Gruntfile.js', '!{,*/}require.js', '!{,*/}angular*.js']
                    dest: '.temp/<%= plugin.name %>/scripts/libs'
                    expand: true
                    flatten: true
                ]
            # Copies the contents of the temp directory excluding views and styles to the buildbot_www directory.
            # In 'dev' individual files are used.
            dev:
                files: [
                    cwd: '.temp/<%= plugin.name %>'
                    src: ['**', '!views/**', '!styles/**']
                    dest: 'buildbot_www'
                    expand: true
                ]
            # Copies select files from the temp directory to the buildbot_www directory.
            # In 'prod' minified files are used along with img and libs.
            # The buildbot_www artifacts contain only the files necessary to run the application.
            prod:
                files: [
                    cwd: '.temp/<%= plugin.name %>'
                    src: ['**', '!views/**', '!styles/**', '!scripts/**', '!scripts-temp/**']
                    dest: 'buildbot_www'
                    expand: true
                ]
            # Copies images to temp without compression.
            img:
                files: [
                    cwd: 'src'
                    src: ['img/**/*.{png,jpg,gif}']
                    dest: '.temp/<%= plugin.name %>'
                    expand: true
                ]
            # Copies js files to the temp directory
            js:
                files: [
                    cwd: 'src'
                    src: 'scripts/**/*.js'
                    dest: '.temp/<%= plugin.name %>'
                    expand: true
                ]
            # Copies coffee src files to the buildbot_www directory
            src:
                files: [
                    cwd: 'src'
                    src: 'scripts/**/*.coffee'
                    dest: 'buildbot_www/src'
                    expand: true
                    flatten: true
                ]
            # Task is run when a watched script is modified.
            scripts:
                files: [
                    cwd: '.temp/<%= plugin.name %>'
                    src: ['scripts/**/*.js', 'scripts/**/*.js.map', '!scripts/test/**']
                    dest: 'buildbot_www'
                    expand: true
                ]
            # Task is run when a watched style is modified.
            styles:
                files: [
                    cwd: '.temp/<%= plugin.name %>'
                    src: 'styles/styles.css'
                    dest: 'buildbot_www'
                    expand: true
                    flatten: true
                ]
            # Task is run when a watched view is modified.
            views:
                files: [
                    cwd: '.temp/<%= plugin.name %>'
                    src: 'views/**/*.html'
                    dest: 'buildbot_www'
                    expand: true
                ]

        # Pre-minifier for AngularJS application.
        ngmin:
            build:
                files: [
                    cwd: '.temp/<%= plugin.name %>/scripts-temp'
                    src: '**/*.js'
                    dest: '.temp/<%= plugin.name %>/scripts'
                    expand: true
                ]

        # Minify JS files with UglifyJS.
        uglify:
            prod:
                files: [
                    src: ['.temp/<%= plugin.name %>/scripts/libs/**/*.js', '.temp/<%= plugin.name %>/scripts/{routes,views,config,*/**}.js']
                    dest: '.temp/<%= plugin.name %>/main.js'
                ]

        # Runs unit tests using karma
        karma:
            options:
                preprocessors:
                    '../**/*.coffee': ['coffee']
                coffeePreprocessor:
                    options:
                        bare: true
                        sourceMap: true
                files: [
                    'bower_components/angular/angular.js'
                    'bower_components/angular-mocks/angular-mocks.js'
                    # TODO Andras: it works when main project is in prod, not dev
                    '../buildbot_www/scripts/scripts.min.js'
                    '../buildbot_www/scripts/test/main.js'
                    'src/scripts/**/*.coffee'
                    'test/**/*.js'
                    'test/**/*.coffee'
                ]
            dev:
                options:
                    frameworks: ['jasmine', 'requirejs'],
                    browsers: ['Chrome', 'PhantomJS']
                    autoWatch: false
            ci:
                options:
                    frameworks: ['jasmine', 'requirejs'],
                    browsers: ['PhantomJS']
                    singleRun: true

        # Sets up file watchers and runs tasks when watched files are changed.
        watch:
            coffee:
                files: 'src/scripts/**/*.coffee'
                tasks: [
                    'newer:coffee:dev'
                    'newer:copy:scripts'
                    'karma:dev:run'
                ]
            coffeetest:
                files: 'test/**/*.coffee'
                tasks: [
                    'karma:dev:run'
                ]
            scripts:
                files: 'src/scripts/**/*.js'
                tasks: [
                    'newer:copy:js'
                    'newer:copy:scripts'
                    'requiregen'
                    'karma:dev:run'
                ]
            styles:
                files: 'src/styles/**/*.less'
                tasks: [
                    'newer:less:dev'
                    'copy:styles'
                ]
            views:
                files: 'src/views/**/*.jade'
                tasks: [
                    'newer:jade:compile'
                    'newer:copy:views'
                ]
            livereload:
                files: 'buildbot_www/**'
                options:
                    livereload: true

        # Run some tasks in parallel to speed up the build process.
        concurrent:
            dev: [
                'coffee:dev'
                'jade'
                'less:dev'
                'copy:bower'
                'copy:js'
            ]
            prod: [
                'coffee:prod'
                'jade'
                'less:prod'
                'copy:bower'
                'copy:js'
            ]

    # Compiles the app with non-optimized build settings and places the build artifacts in the buildbot_www directory.
    # Enter the following command at the command line to execute this build task:
    # grunt
    grunt.registerTask 'default', [
        'dev'
    ]

    # Compiles the app with non-optimized build settings, places the build artifacts in the buildbot_www directory, and watches for file changes.
    # Enter the following command at the command line to execute this build task:
    # grunt dev
    grunt.registerTask 'dev', [
        'clean:working'
        'concurrent:dev'
        'requiregen'
        'copy:views'
        'copy:styles'
        'copy:img'
        'copy:src'
        'copy:dev'
        'watch'
    ]

    # Compiles the app with non-optimized build settings, places the build artifacts in the buildbot_www directory, and runs unit tests.
    # Enter the following command at the command line to execute this build task:
    # grunt ci
    grunt.registerTask 'ci', [
        'karma:ci'
    ]

    # Compiles the app with optimized build settings and places the build artifacts in the buildbot_www directory.
    # Enter the following command at the command line to execute this build task:
    # grunt prod
    grunt.registerTask 'prod', [
        'clean:working'
        'concurrent:prod'
        'ngtemplates'
        'ngmin'
        'uglify'
        'imagemin'
        'copy:styles'
        'copy:prod'
    ]