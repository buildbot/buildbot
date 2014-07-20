  module.exports = function(config) {
    config.set({
    	basePath: "buildbot_www",
        frameworks: ['jasmine'],
        reporters: ['progress'],
        browsers: ['PhantomJS'],
        logLevel: "LOG_DEBUG",
        plugins: [
          'karma-jasmine',
          'karma-phantomjs-launcher',
          'karma-sourcemap-loader'
        ],
        preprocessors: {
          '**/*.js': ['sourcemap']
        },
        files: [
            'scripts.js',
            'dataspec.js',
            'tests.js'
         ]
   });
  };
