### ###############################################################################################
#
#   Concatenate bower.json files into config.js.
#
### ###############################################################################################
module.exports =

    bower_config:
        src: 'src/libs/**/bower.json'
        dest: '<%= dir.temp %>/scripts/config.js'
        options:
            separator:','
            banner: "angular.module('app').constant('bower_configs', ["
            footer: ']);'