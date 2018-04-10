class GlPageWithSidebar extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "page"
            templateUrl: "views/page_with_sidebar.html"
            controller: "_glPageWithSidebarController"
        }

class _glPageWithSidebar extends Controller
    constructor: (@$scope, glMenuService, @$timeout, @$window) ->

        # by default, pin sidebar only if window is wide enough (collapse by default if narrow)
        @sidebarPinned = @$window.innerWidth > 800
        # If user has previously pinned or unpinned the sidebar, use the saved value from localStorage
        sidebarWasPinned = @$window.localStorage.sidebarPinned
        if ( sidebarWasPinned == "true" || sidebarWasPinned == "false" ) # note -- localstorage only stores strings,  converts bools to string.
            @sidebarPinned = sidebarWasPinned != "false"

        @groups = glMenuService.getGroups()
        @footer = glMenuService.getFooter()
        @appTitle = glMenuService.getAppTitle()
        @activeGroup = glMenuService.getDefaultGroup()
        @inSidebar = false
        @sidebarActive = @sidebarPinned

    toggleSidebarPinned: () ->
        @sidebarPinned=!@sidebarPinned
        @$window.localStorage.sidebarPinned = @sidebarPinned

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
