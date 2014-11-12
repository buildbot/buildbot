describe 'topbar-contextual-actions', ->
    beforeEach (module("guanlecoja.ui"))
    elmBody = scope = null

    injected = ($rootScope, $compile) ->
        elmBody = angular.element(
            '<gl-topbar-contextual-actions></gl-contextual-actions>'
        )

        scope = $rootScope.$new()
        $compile(elmBody)(scope)
        scope.$digest()

    beforeEach (inject(injected))

    # simple test to make sure the directive loads
    it 'should load', ->
        expect(elmBody).toBeDefined()
        # should be empty at init
        expect(elmBody.find("li").length).toEqual(0)


    # create the buttons via API
    it 'should create buttons', inject (glTopbarContextualActionsService) ->
        expect(elmBody).toBeDefined()
        called = 0
        glTopbarContextualActionsService.setContextualActions [
            caption:"foo"
            action: -> called++
        ,
            caption:"bar"
            action: -> called++
            ],

        # need two digests to propagate
        scope.$digest()
        scope.$digest()
        expect(elmBody.find("span").length).toEqual(2)
        expect(elmBody.find("button").text()).toEqual("foobar")

        # make sure action is called on click
        elmBody.find("button").each ->
            $(this).click()
        scope.$digest()
        expect(called).toEqual(2)
