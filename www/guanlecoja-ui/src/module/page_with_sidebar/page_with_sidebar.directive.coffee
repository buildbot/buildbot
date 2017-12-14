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
    constructor: (@$scope, glMenuService, @$timeout, @$window) ->
        @sidebarPinned = false; # originally used "@$window.innerWidth > 800". Ideally this would be driven off a user setting that remembered whether it was pinned last time
        @groups = glMenuService.getGroups()
        @footer = glMenuService.getFooter()
        @appTitle = glMenuService.getAppTitle()
        @activeGroup = glMenuService.getDefaultGroup()
        @inSidebar = false
        @sidebarActive = @sidebarPinned

    toggleGroup: (group) ->
        if @activeGroup!=group
            @activeGroup=group
        else
            @activeGroup=null

    enterSidebar: ->
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
            unless @inSidebar or @sidebarPinned
                @sidebarActive = false
                @activeGroup = null
            ), 500
