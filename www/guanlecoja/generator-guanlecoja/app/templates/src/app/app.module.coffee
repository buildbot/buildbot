# first thing, we install underscore.string inside lodash
_.mixin(_.string.exports())

angular.module 'app', [
    'ui.bootstrap'
    'ui.router'
]

angular.module('app').config [ '$urlRouterProvider',
    ($urlRouterProvider) ->

        $urlRouterProvider.otherwise('/home')
        # all states config are in the modules
]
