/* *///###########################################################################################
//
//   This module contains all configuration for the build process
//
/* *///###########################################################################################
const ANGULAR_TAG = "~1.5.3";

const config = {

    /* *///#######################################################################################
    //   Name of the plugin
    /* *///#######################################################################################
    name: 'nestedexample',


    /* *///#######################################################################################
    //   Directories
    /* *///#######################################################################################
    dir: {
        // The build folder is where the app resides once it's completely built
        build: 'buildbot_nestedexample/static'
    },

    /* *///#######################################################################################
    //   Bower dependencies configuration
    /* *///#######################################################################################
    bower: {
        testdeps: {
            jquery: {
                version: '2.1.1',
                files: 'dist/jquery.js'
            },
            angular: {
                version: ANGULAR_TAG,
                files: 'angular.js'
            },
            lodash: {
                version: "~2.4.1",
                files: 'dist/lodash.js'
            },
            "angular-mocks": {
                version: ANGULAR_TAG,
                files: "angular-mocks.js"
            }
        }
    },

    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures'],

    karma: {
        // we put tests first, so that we have angular, and fake app defined
        files: ["tests.js", "scripts.js", 'fixtures.js', "mode-python.js"]
    }
};
module.exports = config;
