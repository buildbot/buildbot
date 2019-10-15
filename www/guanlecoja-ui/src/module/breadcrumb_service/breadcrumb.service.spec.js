/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('breadcrumbService', function() {
    beforeEach(angular.mock.module("guanlecoja.ui"));

    // simple test to make sure the directive loads
    it('should forward call to setBreadcrumb via $broadcast',
       inject(function($rootScope, glBreadcrumbService) {
        let gotBreadcrumb = null;
        $rootScope.$on("glBreadcrumb", (e, data) => gotBreadcrumb = data);

        glBreadcrumbService.setBreadcrumb({foo:"bar"});
        $rootScope.$digest();
        expect(gotBreadcrumb).toEqual({foo:"bar"});
    })
    );
});
