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
    constructor: (@$scope, glMenuService, @$timeout) ->
        @$scope.groups = glMenuService.getGroups()
    toggleGroup: (group) ->
        if @activeGroup!=group
            @activeGroup=group
        else
            @activeGroup=null
    enterSidebar: ->
        @sidebarActive = 1
        @inSidebar = 1

    leaveSidebar: ->
        @inSidebar = 0
        if @timeout?
            @$timeout.cancel(@timeout)
            @timeout = undefined
        @timeout = @$timeout =>
            unless @inSidebar
                @sidebarActive = 0
                @activeGroup = null
        , 500

