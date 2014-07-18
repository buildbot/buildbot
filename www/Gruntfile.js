/*global module*/
module.exports = function (grunt) {
    "use strict";

    // Configuration goes here
    grunt.initConfig({

        // Metadata.
        meta: {
            basePath: '/',
            srcPath: 'sass',
            deployPath: 'css'
        },
        // compass
        compass: {                  // Task
            dev: {                    // Another target
                options: {
                    sassDir: '<%= meta.srcPath %>',
                    cssDir: '<%= meta.deployPath %>',
                    debugInfo: true,
                    environment: "development"
                }
            },
            prod: {                    // Another target
                options: {
                    sassDir: '<%= meta.srcPath %>',
                    cssDir: 'prod/<%= meta.deployPath %>',
                    environment: "production"
                }
            }
        },
        // javascript compression. This task is only used for test results.

        uglify: {
            my_target: {
                files: {
                    'prod/script/logoutput.min.js': ['script/libs/jquery.js', 'script/plugins/jquery-datatables.js', 'script/log.js']
                }
            }
        },

        requirejs: {
            compile: {
                options: {
                    baseUrl: 'script/',
                    mainConfigFile: 'script/main.js',
                    name: 'main',
                    dir: "prod/script",
                    optimize: 'uglify2',
                    preserveLicenseComments: false,
                    generateSourceMaps: true,
                    fileExclusionRegExp: /^test$|^karma\.config\.js|^coverage$/
                }
            }
        },
        // watch
        watch: {
            css: {
                files: [
                    '<%= meta.srcPath %>/**/*.scss'
                ],
                tasks: ['compass:dev'],
                options: {
                    livereload: true // refreshes the browser on changes install an extension for your browser for this
                }

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
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-requirejs');
    grunt.loadNpmTasks('grunt-karma');

    // Define your tasks here
    grunt.registerTask('default', ['compass']);
    grunt.registerTask('default', ['uglify']);
    grunt.registerTask('default', ['requirejs']);
    grunt.registerTask('prod', ['compass:prod', 'requirejs:compile']); // grunt prod for production
    grunt.registerTask('test', ["karma:unit"]);

};
