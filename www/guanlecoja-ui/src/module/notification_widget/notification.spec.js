/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('notification', function() {
    let scope;
    beforeEach(angular.mock.module("guanlecoja.ui"));
    let elmBody = (scope = null);

    const injected = function($rootScope, $compile) {
        elmBody = angular.element(
            '<gl-notification></gl-notification>'
        );

        scope = $rootScope;
        $compile(elmBody)(scope);
        return scope.$digest();
    };

    beforeEach((inject(injected)));

    // simple test to make sure the directive loads
    it('should load', function() {
        expect(elmBody).toBeDefined();
        // if there is an ul, the sidebar has been created
        expect(elmBody.find("ul").length).toBeGreaterThan(0);
    });

    // simple test to make sure the directive loads
    it('should dismiss pass through', inject(function(glNotificationService) {
        let called = false;
        const e =
            {stopPropagation() { return called = true; }};
        spyOn(glNotificationService, "dismiss").and.returnValue(null);
        scope.n.dismiss(2, e);
        expect(glNotificationService.dismiss).toHaveBeenCalledWith(2);
        expect(called).toBe(true);
    })
    );
});
