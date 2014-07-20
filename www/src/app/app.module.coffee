# first thing, we install underscore.string inside lodash
_.mixin(_.str.exports())

angular.module 'app', [
    'ngAnimate'
    'ui.bootstrap'
    'ui.router'
    'restangular'
    'RecursionHelper'
]
