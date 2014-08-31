class GlTopbar extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "page"
            templateUrl: "guanlecoja.ui/views/topbar.html"
            controller: "_glTopbarController"
        }

class _glTopbar extends Controller
    constructor: ($scope, glMenuService, $location) ->
        groups = glMenuService.getGroups()
        groups = _.zipObject(_.map(groups, (g) -> g.name), groups)
        $scope.appTitle = glMenuService.getAppTitle()

        $scope.$on "$stateChangeStart", (ev, state) ->
            $scope.breadcrumb = []
            if state.data?.group
                $scope.breadcrumb.push
                    caption: groups[state.data.group].caption
            $scope.breadcrumb.push
                caption: state.data?.caption or _.humanize(state.name)
                href: '#' + $location.hash()

        $scope.$on "glBreadcrumb", (e, data) ->
            $scope.breadcrumb = data
