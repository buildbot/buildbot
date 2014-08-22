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
        @groups = glMenuService.getGroups()
        @footer = glMenuService.getFooter()
        @appTitle = glMenuService.getAppTitle()
        @activeGroup = null
        @inSidebar = false
        @sidebarActive = false

    toggleGroup: (group) ->
        if @activeGroup!=group
            @activeGroup=group
        else
            @activeGroup=null

    enterSidebar: ->
        @sidebarActive = true
        @inSidebar = true

    hideSidebar: ->
        @sidebarActive = false
        @inSidebar = false

    leaveSidebar: ->
        @inSidebar = false
        if @timeout?
            @$timeout.cancel(@timeout)
            @timeout = undefined
        @timeout = @$timeout (=>
            unless @inSidebar
                @sidebarActive = false
                @activeGroup = null
            ), 500

