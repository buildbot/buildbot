/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class GlTopbarContextualActions {
    constructor() {
        return {
            replace: true,
            restrict: 'E',
            scope: true,
            template: require('./topbar-contextual-actions.tpl.jade'),
            controller: "_glTopbarContextualActionsController"
        };
    }
}


class _glTopbarContextualActions {
    constructor($scope, $sce) {

        $scope.$on("$stateChangeStart", (ev, state) => $scope.actions = []);

        $scope.$on("glSetContextualActions", function(e, data) {
            for (let item of Array.from(data)) {
                if (item.extra_class == null) {
                    item.extra_class = "";
                }
            }

            return $scope.actions = data;
        });
    }
}

// a simple service to abstract TopbarContextualActions configuration
class glTopbarContextualActions {
    constructor($rootScope) { this.$rootScope = $rootScope; ({}); }

    setContextualActions(actions) {
        this.$rootScope.$broadcast("glSetContextualActions", actions);
    }
}


angular.module('guanlecoja.ui')
.directive('glTopbarContextualActions', [GlTopbarContextualActions])
.controller('_glTopbarContextualActionsController', ['$scope', '$sce', _glTopbarContextualActions])
.service('glTopbarContextualActionsService', ['$rootScope', glTopbarContextualActions]);
