class GlPageWithSidebar extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "page"
            templateUrl: "guanlecoja.ui/views/page_with_sidebar.html"
            controller: "_glPageWithSidebarController"
        }

class _glPageWithSidebar extends Controller
    constructor: ($scope, glMenuProvider) ->
        $scope.groups = glMenuProvider.getGroups()
    toggleGroup: (group) ->
        if @activeGroup!=group
            @activeGroup=group
        else
            @activeGroup=null

