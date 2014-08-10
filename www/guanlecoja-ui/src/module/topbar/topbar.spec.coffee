describe 'topbar', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
          '<gl-topbar></gl-topbar>'
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
