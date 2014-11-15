describe 'page with sidebar', ->
    beforeEach (module("app"))
    elmBody = scope = rootScope = queries = timeout = null
    padding = (pix) -> type:"padding", height:pix
    elements = (start, end) -> type:"elements", start:start, end:end

    assertDOM = (l) ->
        childs = []
        $("div", elmBody).each (i, c) -> childs.push(c)
        for item in l
            if item.type == "padding"
                c = childs.shift()
                expect($(c).hasClass("padding")).toBe(true, c.outerHTML)
                expect($(c).height()).toEqual(item.height, c.outerHTML)
            if item.type == "elements"
                for i in [item.start..item.end]
                    c = childs.shift()
                    expect($(c).hasClass("padding")).toBe(false, c.outerHTML)
                    expect(c.innerText).toEqual(i.toString() + "a" + i.toString(), c.outerHTML)
    printDOM = ->
        $("div", elmBody).each ->
            if $(this).hasClass("padding")
                console.log "padding", $(this).height()
            else
                console.log "row", @innerText, $(this).height()

    scrollTo = (pos, verifyPos) ->
        verifyPos ?= pos
        # we scroll pos
        elmBody.scrollTop(pos)
        # make sure that worked
        expect(elmBody.scrollTop()).toBe(verifyPos)

        # as the scroll is automatic, we need to force the event
        elmBody.trigger("scroll")

        timeout.flush()
        # make sure it did not changed
        expect(elmBody.scrollTop()).toBe(verifyPos)

    beforeEach inject ($rootScope, $compile, glMenuService, $timeout, $q, $document) ->
        timeout = $timeout
        queries = []
        rootScope = $rootScope
        elmBody = angular.element(
            '<div scroll-viewport style="height:50px">'+
            '<div style="height:10px" total-size="1000" scroll="item in items">{{::$index}}a{{::item.v}}'+
            '</div></div>'
        )
        scope = $rootScope.$new()

        scope.items =
            get: (index, num) ->
                queries.push([index, num])
                d = $q.defer()
                $timeout ->
                    ret = []
                    ret.push(v:(index + i)) for i in [0..num - 1]
                    d.resolve(ret)
                return d.promise
        $compile(elmBody)(scope)[0]
        scope.$digest()

        # we need to append to body, so that the element is styled properly, and gets a height
        elmBody.appendTo("body")

    # ViewPort height is 50, and item height is 10, so a screen should contain 5 item
    it 'should initially load 2 screens', inject ($timeout) ->
        $timeout.flush()
        expect(queries).toEqual([[0,10]])
        assertDOM [
            elements(0,9)
            padding(9900)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

    it 'if scroll to middle, should load 3 screens', inject ($timeout) ->
        # initial load
        $timeout.flush()

        scrollTo(600)

        expect(queries).toEqual([[0,10], [55, 15]])
        assertDOM [
            elements(0,9)   # 100
            padding(450)    # 550
            elements(55,69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

    it 'several scroll loads several screens, and paddings are cleaned out', inject ($timeout) ->
        # initial load
        $timeout.flush()

        scrollTo(600)
        expect(queries).toEqual([[0,10], [55, 15]])
        assertDOM [
            elements(0,9)   # 100
            padding(450)    # 550
            elements(55,69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

        scrollTo(400)
        expect(queries).toEqual([[0,10], [55, 15], [35, 15]])
        assertDOM [
            elements(0,9)   # 100
            padding(250)    # 350
            elements(35,49) # 500
            padding(50)    # 550
            elements(55,69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

        scrollTo(500)
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5]])
        assertDOM [
            elements(0,9)   # 100
            padding(250)    # 350
            elements(35, 69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

        scrollTo(100)
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10]])
        assertDOM [
            elements(0,19)   # 200
            padding(150)    # 350
            elements(35, 69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

        scrollTo(200)
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10], [20, 10]])
        assertDOM [
            elements(0,29)   # 300
            padding(50)      # 350
            elements(35, 69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

        scrollTo(300)
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10], [20, 10], [30, 5]])
        assertDOM [
            elements(0,69) # 700
            padding(10000 - 700)
        ]
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10)

    it 'Scroll to the end', inject ($timeout) ->
        # initial load
        $timeout.flush()
        scrollTo(10000, 9950)

        expect(queries).toEqual([[0,10], [990, 10]])
        assertDOM [
            elements(0,9)   # 100
            padding(9800)   # 9900
            elements(990, 999) # 10000
        ]
