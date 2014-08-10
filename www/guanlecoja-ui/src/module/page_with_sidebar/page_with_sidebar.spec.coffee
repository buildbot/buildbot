describe 'page with sidebar', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
          '<gl-page-with-sidebar></gl-page-with-sidebar>'
        )

        scope = $rootScope;
        $compile(elmBody)(scope);
        scope.$digest();

    beforeEach (inject(injected))

    # simple test to make sure the directive loads
    it 'should load', ->
        expect(elmBody).toBeDefined()
        # if there is an ul, the sidebar has been created
        expect(elmBody.find("ul").length).toBeGreaterThan(0)
