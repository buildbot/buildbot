# first thing, we install underscore.string inside lodash
require ['underscore.string'], (_str) ->
    _.mixin(_str.exports())

angular.module 'app', [
    'ngAnimate'
    'ui.bootstrap'
    'ui.router'
    'restangular'
    'RecursionHelper'
]
