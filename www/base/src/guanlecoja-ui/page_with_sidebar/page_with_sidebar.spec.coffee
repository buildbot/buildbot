describe 'page with sidebar', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = rootScope = null

    injected = ($rootScope, $compile, glMenuService, $window) ->
        rootScope = $rootScope
        elmBody = angular.element(
          '<gl-page-with-sidebar></gl-page-with-sidebar>'
        )
        groups = [
            name: 'g1'
            items: [name:'i1', 'sref': ".."]
        ,
            name: 'g2'
        ]
        $window.localStorage.sidebarPinned = "false"
        glMenuService.getGroups = -> groups
        glMenuService.getDefaultGroup = -> groups[1]
        scope = $rootScope;
        $compile(elmBody)(scope);
        scope.$digest();

    beforeEach (inject(injected))

    # simple test to make sure the directive loads
    it 'should load', ->
        expect(elmBody).toBeDefined()
        # if there is an ul, the sidebar has been created
        expect(elmBody.find("ul").length).toBeGreaterThan(0)

    it 'should behave', inject ($timeout) ->
        expect(elmBody).toBeDefined()
        g = scope.page.groups[1]

        expect(scope.page.activeGroup).toBe(g)
        scope.page.toggleGroup(g)
        expect(scope.page.activeGroup).toBe(null)
        scope.page.toggleGroup(g)
        expect(scope.page.activeGroup).toBe(g)

        # sidebar should get pinned state from localStorage.sidebarPinned
        expect(scope.page.sidebarPinned).toBe(false)

        $timeout.flush()
        expect(scope.page.sidebarActive).toBe(true)
        scope.page.sidebarPinned = false
        scope.page.leaveSidebar()
        $timeout.flush()
        expect(scope.page.sidebarActive).toBe(false)
        scope.page.sidebarPinned = false
