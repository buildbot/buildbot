/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('page with sidebar', function() {
    let rootScope, scope;
    beforeEach((module("guanlecoja.ui")));
    let elmBody = (scope = (rootScope = null));

    const injected = function($rootScope, $compile, glMenuService, $window) {
        rootScope = $rootScope;
        elmBody = angular.element(
          '<gl-page-with-sidebar></gl-page-with-sidebar>'
        );
        const groups = [{
            name: 'g1',
            items: [{name:'i1', 'sref': ".."}]
        }
        ,
            {name: 'g2'}
        ];
        $window.localStorage.sidebarPinned = "false";
        glMenuService.getGroups = () => groups;
        glMenuService.getDefaultGroup = () => groups[1];
        scope = $rootScope;
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    beforeEach((inject(injected)));

    // simple test to make sure the directive loads
    it('should load', function() {
        expect(elmBody).toBeDefined();
        // if there is an ul, the sidebar has been created
        return expect(elmBody.find("ul").length).toBeGreaterThan(0);
    });

    it('should toggle groups', function() {
        expect(elmBody).toBeDefined();
        const g = scope.page.groups[1];

        expect(scope.page.activeGroup).toBe(g);
        scope.page.toggleGroup(g);
        expect(scope.page.activeGroup).toBe(null);
        scope.page.toggleGroup(g);
        expect(scope.page.activeGroup).toBe(g);
    });

    it('should pin sidebar', inject(function($timeout, $window) {
        expect(scope.page.sidebarPinned).toBe(false);
        $timeout.flush();

        if ($window.innerWidth > 800) {
            expect(scope.page.sidebarActive).toBe(true);
        } else {
            expect(scope.page.sidebarActive).toBe(false);
        }

        scope.page.sidebarPinned = false;
        scope.page.leaveSidebar();
        $timeout.flush();
        expect(scope.page.sidebarActive).toBe(false);
        return scope.page.sidebarPinned = false;
    }));
});
