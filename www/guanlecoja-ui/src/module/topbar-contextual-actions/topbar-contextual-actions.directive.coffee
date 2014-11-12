class GlTopbarContextualActions extends Directive
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: true
            templateUrl: "guanlecoja.ui/views/topbar-contextual-actions.html"
            controller: "_glTopbarContextualActionsController"
        }


class _glTopbarContextualActions extends Controller
    constructor: ($scope, $sce) ->

        $scope.$on "$stateChangeStart", (ev, state) ->
            $scope.actions = []

        $scope.$on "glSetContextualActions", (e, data) ->
            for item in data
                item.extra_class ?= ""

            $scope.actions = data

# a simple service to abstract TopbarContextualActions configuration
class glTopbarContextualActions extends Service
    constructor: (@$rootScope) -> {}

    setContextualActions: (actions) ->
        @$rootScope.$broadcast("glSetContextualActions", actions)
