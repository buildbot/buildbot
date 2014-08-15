describe 'page with sidebar', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = rootScope = null

    injected = ($rootScope, $compile, glMenuService) ->
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
        glMenuService.getGroups = -> groups
        console.log glMenuService.getGroups()
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

        scope.page.toggleGroup(g)
        expect(scope.page.activeGroup).toBe(g)
        scope.page.toggleGroup(g)
        expect(scope.page.activeGroup).toBe(null)

        scope.page.enterSidebar()
        expect(scope.page.sidebarActive).toBe(true)
        scope.page.leaveSidebar()
        expect(scope.page.sidebarActive).toBe(true)
        scope.page.enterSidebar()
        expect(scope.page.sidebarActive).toBe(true)
        scope.page.leaveSidebar()
        $timeout.flush()
        expect(scope.page.sidebarActive).toBe(false)
