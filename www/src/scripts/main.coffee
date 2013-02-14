# @maybetodo find a way to generate this file automatically
# based on dependancy decoration we could put in the coffeescript's header
require
        shim:
                'directives/topmenu'                 : deps: ['app']
                'controllers/homeController'         : deps: ['app']
                'controllers/buildersController'     : deps: ['app','services/buildbotService']
                'controllers/changesController'      : deps: ['app','services/buildbotService']
                'filters/twitterfy'                  : deps: ['app']
                'libs/angular-resource'              : deps: ['libs/angular']
                'responseInterceptors/dispatcher'    : deps: ['app']
                'services/recentStorage'             : deps: ['app']
                'services/buildbotService'           : deps: ['app']
                'app'                                : deps: ['libs/angular', 'libs/angular-resource', 'libs/ng-grid' ]
                'libs/ng-grid'                       : deps: ['libs/angular']
                'libs/angular'                       : deps: ['libs/jquery.min']
                'bootstrap'                          : deps: ['app']
                'routes'                             : deps: ['app']
                'run'                                : deps: ['app']
        [
                'require'
                'directives/topmenu'
                'controllers/homeController'
                'controllers/buildersController'
                'controllers/changesController'
                'services/recentStorage'
                'services/buildbotService'
                'filters/twitterfy'
                'responseInterceptors/dispatcher'
                'routes'
                'run'
        ], (require) ->
                require ['bootstrap']
