describe 'breadcrumbService', ->
    beforeEach module "guanlecoja.ui"

    # simple test to make sure the directive loads
    it 'should forward call to setBreadcrumb via $broadcast', inject ($rootScope, glBreadcrumbService) ->
        gotBreadcrumb = null
        $rootScope.$on "glBreadcrumb", (e, data) ->
            gotBreadcrumb = data

        glBreadcrumbService.setBreadcrumb(foo:"bar")
        $rootScope.$digest()
        expect(gotBreadcrumb).toEqual(foo:"bar")
