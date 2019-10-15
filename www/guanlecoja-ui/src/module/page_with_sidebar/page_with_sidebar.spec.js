/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('page with sidebar', function() {
    let rootScope, scope;
    beforeEach(angular.mock.module("guanlecoja.ui"));
    let elmBody = (scope = (rootScope = null));

    const injected = function($rootScope, $compile, glMenuService) {
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
        glMenuService.getGroups = () => groups;
        glMenuService.getDefaultGroup = () => groups[1];
        scope = $rootScope;
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    describe('default window', function() {
        beforeEach(inject(injected));

        it('should load', function() {
            // simple test to make sure the directive loads
            expect(elmBody).toBeDefined();
            // if there is an ul, the sidebar has been created
            expect(elmBody.find("ul").length).toBeGreaterThan(0);
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
    });

    [
        [750, "false", "small window, stored sidebarPinned==false"],
        [750, "true", "small window, stored sidebarPinned==true"],
        [750, undefined, "small window, stored sidebarPinned==undefined"],
        [850, "false", "large window, stored sidebarPinned==false"],
        [850, "true", "large window, stored sidebarPinned==true"],
        [850, undefined, "large window, stored sidebarPinned==undefined"],
    ].forEach(([innerWindowWidth, storedSidebarPinned, description]) => {
        describe(description, function() {

            beforeEach(function() {
                mockWindow = {
                    innerWidth: innerWindowWidth,
                    localStorage: {
                        sidebarPinned: storedSidebarPinned
                    },
                    document: new Document()
                };

                angular.mock.module(function($provide){
                    $provide.value('$window', mockWindow);
                });
            });

            beforeEach(inject(injected));

            it('should pin sidebar', inject(function($timeout) {
                if (storedSidebarPinned === "true" ||
                    (storedSidebarPinned === undefined && innerWindowWidth > 800))
                {
                    expect(scope.page.sidebarPinned).toBe(true);
                    expect(scope.page.sidebarActive).toBe(true);
                } else {
                    expect(scope.page.sidebarPinned).toBe(false);
                    expect(scope.page.sidebarActive).toBe(false);
                }

                scope.page.sidebarPinned = false;
                scope.page.leaveSidebar();
                $timeout.flush();
                expect(scope.page.sidebarActive).toBe(false);
                scope.page.sidebarPinned = false;
            }));
        });
    });
});
