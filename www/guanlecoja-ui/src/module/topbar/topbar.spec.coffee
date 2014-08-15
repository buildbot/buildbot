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

    # simple test to make sure the directive loads
    it 'should update breadcrumb upon messages', inject ($location)->
        $location.hash = -> "bar/"
        scope.$broadcast "$stateChangeStart",
            name: "foo"
        expect(scope.breadcrumb).toEqual([ { caption : 'Foo', href : '#bar/' } ])

        scope.$broadcast "breadcrumb", [
            caption: "bar"
            sref: "foo"
        ]
        expect(scope.breadcrumb).toEqual([ { caption : 'bar', sref : 'foo' } ])
