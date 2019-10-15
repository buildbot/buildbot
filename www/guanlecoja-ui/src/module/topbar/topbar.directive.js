/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class GlTopbar {
    constructor() {
        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: false,
            controllerAs: "page",
            template: require('./topbar.tpl.jade'),
            controller: "_glTopbarController"
        };
    }
}

class _glTopbar {
    constructor($scope, glMenuService, $location) {
        let groups = glMenuService.getGroups();
        groups = _.zipObject(_.map(groups, g => g.name), groups);
        $scope.appTitle = glMenuService.getAppTitle();

        $scope.$on("$stateChangeStart", function(ev, state) {
            $scope.breadcrumb = [];
            if ((state.data != null ? state.data.group : undefined) && ((state.data != null ? state.data.caption : undefined) !== groups[state.data.group].caption)) {
                $scope.breadcrumb.push({
                    caption: groups[state.data.group].caption});
            }
            return $scope.breadcrumb.push({
                caption: (state.data != null ? state.data.caption : undefined) || _.capitalize(state.name),
                href: `#${$location.hash()}`
            });
        });

        $scope.$on("glBreadcrumb", (e, data) => $scope.breadcrumb = data);
    }
}


angular.module('guanlecoja.ui')
.directive('glTopbar', [GlTopbar])
.controller('_glTopbarController', ['$scope', 'glMenuService', '$location', _glTopbar]);
