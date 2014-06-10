
angular.module('app').config [ '$urlRouterProvider',
    ($urlRouterProvider) ->

        $urlRouterProvider.otherwise('/')
        # all states config are in the modules
]
