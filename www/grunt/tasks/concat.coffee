### ###############################################################################################
#
#   Concatenate bower.json files into config.js.
#
### ###############################################################################################
module.exports =

    bower_config:
        src: 'src/libs/**/bower.json'
        dest: '.temp/scripts/config.js'
        options:
            separator:','
            banner: "angular.module('buildbot.about').constant('bower_configs', ["
            footer: ']);'