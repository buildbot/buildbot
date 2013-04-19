// Build configurations.
module.exports = function (grunt) {
    grunt.initConfig({
        /*
            Deletes built and temp directories.
            The temp directory is used during the build process.
            The built directory contains the artifacts of the build.
            These directories should be deleted before subsequent builds.
        */
        delete: {
            built: {
                files: ['./built/']
            },
            temp: {
                files: ['./temp/']
            }
        },

        // CoffeeScript linting rules.
        coffeeLint: {
            scripts: {
                files: ['./src/scripts/**/*.coffee', './test/scripts/**/*.coffee'],
                // Use one tab for indentation.
                indentation: {
                    value: 4,
                    level: 'error'
                },
                // 78-character maximum line length
                max_line_length: {
                    value: 79,
                    level: 'warn'
                },
                // Using tabs should result in an error.
                no_tabs: {
                    level: 'error'
                }
            }
        },


        // Compile CoffeeScript (.coffee) files to JavaScript (.js).
        coffee: {
            scripts: {
                files: {
                    './temp/scripts/': './src/scripts/**/*.coffee',
                    './test/scripts/': './test/scripts/**/*.coffee'
                },
                // Don't include a surrounding Immediately-Invoked Function Expression (IIFE) in the compiled output.
                // For more information on IIFEs, please visit http://benalman.com/news/2010/11/immediately-invoked-function-expression/
                bare: true
            }
        },

        // Compile LESS (.less) files to CSS (.css).
        less: {
            styles: {
                files: {
                    './temp/styles/styles.css': './src/styles/styles.less'
                }
            }
        },

        /*
            Compile template files (.template) to HTML (.html).

            .template files are essentially html; however, you can take advantage of features provided by grunt such as underscore templating.

            The example below demonstrates the use of the environment configuration setting.
            In 'prod' the concatenated and minified scripts are used along with a unique QueryString parameter to address browser caching.
            In environments other than 'prod' the individual files are used and loaded with RequireJS.

            <% if (config.environment === 'prod') { %>
                <script src="/scripts/scripts.min.js?_=v<%= config.uniqueVersion() %>"></script>
            <% } else { %>
                <script data-main="/scripts/main.js" src="/scripts/libs/require.js"></script>
            <% } %>
        */
        template: {
            views: {
                files: {
                    './temp/views/': './src/views/**/*.template'
                }
            }
        },
        jade: {
            views: {
                files: {'./temp/views':'./src/views/**/*.jade'},
                options: {
                    self:true,
                    client: false
                }
            },
            dev: {
                files: {
                    './temp': './src/*.jade'
                },
                options: {
                    client: false,
                    self:true,
                    pretty:true,
                    locals: {environment:'dev',
                            reloadUrl:"localhost:35729"
                            }
                }
            },
            prod: {
                files: '<config:jade.dev.files>',
                options: {
                    client: false,
                    self:true,
                    locals: {environment:'prod'}
                }
            }
        },
        /*
            Creates a single file consisting of multiple views (html) files surrounded by script tags.

            For example, take the following two files:
                <!-- /temp/views/people.html (compiled from /src/views/people.template) -->
                <ul ng-hide="!people.length">
                    <li class="row" ng-repeat="person in people | orderBy:'name'">
                        <a ng-href="#/people/{{person.id}}" ng-bind="person.name"></a>
                    </li>
                </ul>

                <!-- /temp/views/repos.html (compiled from /src/views/repos.html) -->
                <ul ng-hide="!repos.length">
                    <li ng-repeat="repo in repos | orderBy:'pushed_at':true">
                        <a ng-href="{{repo.url}}" ng-bind="repo.name" target="_blank"></a>
                        <div ng-bind="repo.description"></div>
                    </li>
                </ul>

            AngularJS will interpret inlined scripts with type of "text/ng-template" in lieu of retrieving the view from the server.
            The id of the script tag must match the path requested.
            Since the path includes the temp directory, this must be trimmed.

            The output of the configuration below is:
                <!-- /temp/views/views.html -->
                <script id="/views/people.html" type="text/ng-template">
                    <ul ng-hide="!people.length">
                        <li class="row" ng-repeat="person in people | orderBy:'name'">
                            <a ng-href="#/people/{{person.id}}" ng-bind="person.name"></a>
                        </li>
                    </ul>
                </script>
                <script id="/views/repos.html" type="text/ng-template">
                    <ul ng-hide="!repos.length">
                        <li ng-repeat="repo in repos | orderBy:'pushed_at':true">
                            <a ng-href="{{repo.url}}" ng-bind="repo.name" target="_blank"></a>
                            <div ng-bind="repo.description"></div>
                        </li>
                    </ul>
                </script>

            Now the views.html file can be included in the application and avoid making requests to the server for the views.
        */
        inlineTemplate: {
            views: {
                files: {
                    './temp/views/views.html': './temp/views/**/*.html'
                },
                type: 'text/ng-template',
                trim: 'temp/'
            }
        },

        // Copies directories and files from one location to another.
        copy: {
            // Copies libs and img directories to temp.
            temp: {
                files: {
                    './temp/scripts/libs/': './src/scripts/libs/',
                    './temp/img/': './src/img/',
                    './temp/font/': './src/font/'
                }
            },
            /*
                Copies the contents of the temp directory to the built directory.
                In 'dev' individual files are used.
            */
            dev: {
                files: {
                    './built/': './temp/'
                }
            },
            /*
                Copies select files from the temp directory to the built directory.
                In 'prod' minified files are used along with img and libs.
                The built artifacts contain only the files necessary to run the application.
            */
            prod: {
                files: {
                    './built/img/': './temp/img/',
                    './built/font/': './temp/font/',
                    './built/scripts/': './temp/scripts/scripts.min.js',
                    './built/scripts/libs': ['./temp/scripts/libs/html5shiv-printshiv.js', './temp/scripts/libs/json2.js'],
                    './built/styles/': './temp/styles/styles.min.css',
                    './built/index.html': './temp/index.min.html'
                }
            },
            // Task is run when a watched script is modified.
            scripts: {
                files: {
                    './built/scripts/': './temp/scripts/'
                }
            },
            // Task is run when a watched style is modified.
            styles: {
                files: {
                    './built/styles/': './temp/styles/'
                }
            },
            // Task is run when the watched index.template file is modified.
            index: {
                files: {
                    './built/': './temp/index.html'
                }
            },
            // Task is run when a watched view is modified.
            views: {
                files: {
                    './built/views/': './temp/views/'
                }
            }
        },

        /*
            RequireJS optimizer configuration for both scripts and styles.
            This configuration is only used in the 'prod' build.
            The optimizer will scan the main file, walk the dependency tree, and write the output in dependent sequence to a single file.
            Since RequireJS is not being used outside of the main file or for dependency resolution (this is handled by AngularJS), RequireJS is not needed for final output and is excluded.
            RequireJS is still used for the 'dev' build.
            The main file is used only to establish the proper loading sequence.
        */
        requirejs: {
            scripts: {
                baseUrl: './temp/scripts/',
                findNestedDependencies: true,
                logLevel: 0,
                mainConfigFile: './temp/scripts/main.js',
                name: 'main',
                // Exclude main from the final output to avoid the dependency on RequireJS at runtime.
                onBuildWrite: function (moduleName, path, contents) {
                    var modulesToExclude = ['main'],
                        shouldExcludeModule = modulesToExclude.indexOf(moduleName) >= 0;

                    if (shouldExcludeModule) {
                        return '';
                    }

                    return contents;
                },
                optimize: 'uglify',
                out: './temp/scripts/scripts.min.js',
                preserveLicenseComments: false,
                skipModuleInsertion: true,
                uglify: {
                    // Let uglifier replace variables to further reduce file size.
                    no_mangle: false
                }
            },
            styles: {
                baseUrl: './temp/styles/',
                cssIn: './temp/styles/styles.css',
                logLevel: 0,
                optimizeCss: 'standard',
                out: './temp/styles/styles.min.css'
            }
        },

        /*
            Minifiy index.html.
            Extra white space and comments will be removed.
            Content within <pre /> tags will be left unchanged.
            IE conditional comments will be left unchanged.
            As of this writing, the output is reduced by over 14%.
        */
        minifyHtml: {
            prod: {
                files: {
                    './temp/index.min.html': './temp/index.html'
                }
            }
        },

        // Sets up file watchers and runs tasks when watched files are changed.
        watch: {
            scripts: {
                files: './src/scripts/**/*.coffee',
                tasks: 'coffeeLint:scripts coffee:scripts copy:scripts reload'
            },
            styles: {
                files: './src/styles/**/*.less',
                tasks: 'less copy:styles reload'
            },
            index: {
                files: './src/index.jade',
                tasks: 'jade:dev copy:index reload'
            },
            views: {
                files: './src/views/**/*.template',
                tasks: 'template:views copy:views reload'
            },
            jadeviews: {
                files: './src/views/**/*.jade',
                tasks: 'jade:views copy:views reload'
            }
        },
        /*
            Leverages the LiveReload browser plugin to automatically reload the browser when watched files have changed.

            As of this writing, Chrome, Firefox, and Safari are supported.

            Get the plugin:
            here http://help.livereload.com/kb/general-use/browser-extensions
        */
        reload: {
            liveReload: true,
            port: 35729
        }
    });

    /*
        Register grunt tasks supplied by grunt-hustler.
        Referenced in package.json.
        https://github.com/CaryLandholt/grunt-hustler
    */
    grunt.loadNpmTasks('grunt-hustler');
    grunt.loadNpmTasks('grunt-jade');

    /*
        Register grunt tasks supplied by grunt-reload.
        Referenced in package.json.
        https://github.com/webxl/grunt-reload
    */
    grunt.loadNpmTasks('grunt-reload');

    // A task to run unit tests in testacular.
    grunt.registerTask('unit-tests', 'run the testacular test driver on jasmine unit tests', function () {
        var done = this.async();

        require('child_process').exec('./node_modules/testacular/bin/testacular start ./testacular.conf.js --single-run', function (err, stdout) {
            grunt.log.write(stdout);
            done(err);
        });
    });

    /*
        Compiles the app with non-optimized build settings and places the build artifacts in the built directory.
        Enter the following command at the command line to execute this build task:
        grunt
    */
    grunt.registerTask('default', [
        'delete',
        'coffeeLint',
        'coffee',
        'less',
        'template:views',
        'jade:views',
        'inlineTemplate',
        'jade:dev',
        'copy:temp',
        'copy:dev'
    ]);

    /*
        Compiles the app with non-optimized build settings, places the build artifacts in the built directory, and watches for file changes.
        Enter the following command at the command line to execute this build task:
        grunt dev
    */
    grunt.registerTask('dev', [
        'default',
        'reload',
        'watch'
    ]);

    /*
        Compiles the app with optimized build settings and places the build artifacts in the built directory.
        Enter the following command at the command line to execute this build task:
        grunt prod
    */
    grunt.registerTask('prod', [
        'delete',
        'coffeeLint',
        'coffee',
        'less',
        'template:views',
        'jade:views',
        'inlineTemplate',
        'jade:prod',
        'copy:temp',
        'requirejs',
        'minifyHtml',
        'copy:prod',
        'delete:temp'
    ]);

    /*
        Compiles the app with non-optimized build settings, places the build artifacts in the built directory, and runs unit tests.
        Enter the following command at the command line to execute this build task:
        grunt test
    */
    grunt.registerTask('test', [
        'default',
        'unit-tests'
    ]);
};
