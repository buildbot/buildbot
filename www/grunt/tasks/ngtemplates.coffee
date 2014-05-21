### ###############################################################################################
#
#   Minifying, combining and caching AngularJS templates with $templateCache
#
### ###############################################################################################
module.exports = (grunt, options) ->

    app:
        options:
            # Prefix name if exists
            prefix: options.config.name ? ''
        cwd: '<%= dir.temp %>'
        src: 'views/*.html'
        dest: '<%= dir.temp %>/scripts/app.templates.js'