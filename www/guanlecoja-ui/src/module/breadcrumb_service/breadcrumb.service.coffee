# a simple service to abstract breadcrumb configuration
class glBreadcrumb
    constructor: (@$rootScope) -> {}

    setBreadcrumb: (breadcrumb) ->
        @$rootScope.$broadcast("glBreadcrumb", breadcrumb)



angular.module('app')
.service('glBreadcrumbService', ['$rootScope', glBreadcrumb])