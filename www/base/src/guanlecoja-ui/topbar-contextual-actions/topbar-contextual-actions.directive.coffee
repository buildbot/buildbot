class GlTopbarContextualActions
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: true
            templateUrl: "views/topbar-contextual-actions.html"
            controller: "_glTopbarContextualActionsController"
        }


class _glTopbarContextualActions
    constructor: ($scope, $sce) ->

        $scope.$on "$stateChangeStart", (ev, state) ->
            $scope.actions = []

        $scope.$on "glSetContextualActions", (e, data) ->
            for item in data
                item.extra_class ?= ""

            $scope.actions = data

# a simple service to abstract TopbarContextualActions configuration
class glTopbarContextualActions
    constructor: (@$rootScope) -> {}

    setContextualActions: (actions) ->
        @$rootScope.$broadcast("glSetContextualActions", actions)


angular.module('guanlecoja.ui')
.directive('glTopbarContextualActions', [GlTopbarContextualActions])
.controller('_glTopbarContextualActionsController', ['$scope', '$sce', _glTopbarContextualActions])
.service('glTopbarContextualActionsService', ['$rootScope', glTopbarContextualActions])
