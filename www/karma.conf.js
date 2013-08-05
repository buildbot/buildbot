// list of files / patterns to load in the browser
files = [
    JASMINE,
    JASMINE_ADAPTER,
    './buildbot_www/scripts/libs/angular.js',
    './buildbot_www/scripts/libs/angular-resource.js',
    './buildbot_www/scripts/libs/*.js',
    './buildbot_www/scripts/libs/require.js',
    './buildbot_www/scripts/**/*.js',

    './buildbot_www/scripts/test/filters/*.js',
    './buildbot_www/scripts/test/services/*.js',
    './buildbot_www/scripts/test/controllers/*.js'
];

// level of logging
// possible values: LOG_DISABLE || LOG_ERROR || LOG_WARN || LOG_INFO || LOG_DEBUG
logLevel = LOG_INFO;
