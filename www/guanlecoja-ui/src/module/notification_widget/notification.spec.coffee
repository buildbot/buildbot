describe 'notification', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
          '<gl-notification></gl-notification>'
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
    it 'should dismiss pass through', inject (glNotificationService)->
        called = false
        e =
            stopPropagation: -> called = true
        spyOn(glNotificationService, "dismiss").and.returnValue(null)
        scope.n.dismiss(2, e)
        expect(glNotificationService.dismiss).toHaveBeenCalledWith(2)
        expect(called).toBe(true)

    # simple test to make sure the directive loads
    it 'should toggle', inject (glNotificationService)->
        scope.n.toggle()
        expect(scope.isOpen).toBe(true)
