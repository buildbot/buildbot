/*global module*/
module.exports = function (grunt) {
    "use strict";

    var target = "dev";
    if (grunt.option('prod')) {
        target = "prod";
    }

    // Configuration goes here
    grunt.initConfig({
        files: {
            css: {
                src: ['sass'],
                src_watch: ['sass/**/*.scss'],
                dest: ['prod/css']
            },
            js: {
                src: [
                    'script/libs/**/*.js',
                    'script/plugins/**/*.js',
                    'script/project/**/*.js',
                    'script/main.js',
                    'script/require.js'
                ],
                dest: ['prod/script']
            }
        },
        compass: {
            options: {
                sassDir: '<%= files.css.src %>',
                cssDir: '<%= files.css.dest %>'
            },
            prod: {
                options: {
                    environment: 'production',
                    outputStyle: 'compressed'
                }
            },
            dev: {
                options: {
                    debugInfo: true,
                    environment: 'development',
                    outputStyle: 'nested'
                }
            }
        },
        requirejs: {
            options: {
                baseUrl: 'script/',
                mainConfigFile: 'script/main.js',
                name: 'main',
                dir: "<%= files.js.dest %>",
                preserveLicenseComments: false,
                generateSourceMaps: true,
                fileExclusionRegExp: /^test$|^karma\.config\.js|^coverage$/,
                findNestedDependencies: true
            },
            dev: {
                options: {
                    optimize: 'none'
                }
            },
            prod: {
                options: {
                    optimize: 'uglify2'
                }
            }
        },
        watch: {
            options: {
                livereload: true
            },
            css: {
                files: ['<%= files.css.src_watch %>'],
                tasks: ['compass:' + target]
            },
            js: {
                files: ['<%= files.js.src %>'],
                tasks: ['requirejs:' + target]
            }
        },

        // karma
        karma: {
            unit: {
                configFile: "script/karma.config.js",
                browsers: ["Chrome"],
                singleRun: true,
                runnerPort: 9876
            }
        }
    });

    // Load plugins here
    grunt.loadNpmTasks('grunt-contrib-compass');
    grunt.loadNpmTasks('grunt-contrib-watch'); // run grunt watch for converting sass files to css in realtime
    grunt.loadNpmTasks('grunt-contrib-requirejs');
    grunt.loadNpmTasks('grunt-newer');
    grunt.loadNpmTasks('grunt-karma');

    // Define your tasks here
    grunt.registerTask('default', ['compass:' + target, 'requirejs:' + target, 'watch']);
    grunt.registerTask('build', ['compass:' + target, 'requirejs:' + target]);
    grunt.registerTask('test', ["karma:unit"]);

};
