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
        @sidebarPinned = glMenuService.getPinnedByDefault();
        @pinnedChangedCallback = glMenuService.getPinnedChangedCallback();
        console.log( "_glPageWithSidebar @sidebarPinned", @sidebarPinned )
        @groups = glMenuService.getGroups()
        @footer = glMenuService.getFooter()
        @appTitle = glMenuService.getAppTitle()
        @activeGroup = glMenuService.getDefaultGroup()
        @inSidebar = false
        @sidebarActive = @sidebarPinned

    toggleSidebarPinned: () ->
        @sidebarPinned=!@sidebarPinned
        # callback for application to listen to changes in whether the menu is pinned so 
        #  it can persist this setting.
        if @pinnedChangedCallback
            @pinnedChangedCallback(@sidebarPinned)

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
