# a simple service to abstract breadcrumb configuration
class glBreadcrumb extends Service
    constructor: (@$rootScope) -> {}

    setBreadcrumb: (breadcrumb) ->
        @$rootScope.$broadcast("glBreadcrumb", breadcrumb)

