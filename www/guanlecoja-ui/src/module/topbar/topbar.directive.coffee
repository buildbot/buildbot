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
    constructor: ($scope, glMenuService) ->
        $scope.appTitle = glMenuService.getAppTitle()
        $scope.$on "$stateChangeStart", (ev, state) ->
            console.log state
            $scope.breadcrumb = [
                caption: _.humanize(state.name)
                href: '#' + state.url
            ]
        $scope.$on "breadcrumb", (e, data) ->
            $scope.breadcrumb = data
