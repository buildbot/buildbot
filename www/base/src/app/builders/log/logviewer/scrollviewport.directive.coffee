###
based on https://github.com/Hill30/NGScroller (MIT license)

ui.scroll is a good directive for infinite scrolling. Its inner working makes it not very adapted to viewing log:

This scroll directive uses ui.scroll base, but replace the whole DOM manipulation code
- Can directly scroll to arbitrary position
- Dont remove out-of-sight DOM. Eventually this will result in huge dom, so please make sure to use bind-once childs.
    This however as the advantage on only loading each line once.
- Support line count, and adapt scroll bar appropriately
- Can follow the end of stream, via updating the scroll-position attribute
- row height is fixed (or you cannot make geometric calculation to determine the positions of arbitrary elements)

This directive uses JQuery for DOM manipulation
###
class ScrollViewport extends Directive
    constructor: ($log) ->
        return {
            controller:
                [ '$scope', '$element'
                    (scope, element) ->
                        this.viewport = element
                        this
                ]
        }

class Scroll extends Directive
    constructor: ($log, $injector, $rootScope, $timeout, $window) ->
        return {
            require: ['?^scrollViewport']
            transclude: 'element'
            priority: 1000
            terminal: true
            compile: (elementTemplate, attr, linker) ->
                ($scope, element, $attr, controllers) ->

                    log = $log.debug || $log.log

                    match = $attr.scroll.match(/^\s*(\w+)\s+in\s+([\w\.]+)\s*$/)
                    if !match
                        throw new Error("Expected scroll in form of '_item_ in _datasource_'"+
                            "but got '#{$attr.uiScroll}'")

                    itemName = match[1]
                    datasourceName = match[2]
                    totalSize = null

                    isDatasource = (datasource) ->
                        angular.isObject(datasource) and datasource.get and angular.isFunction(datasource.get)

                    getValueChain = (targetScope, target) ->
                        return null if not targetScope
                        chain = target.match(/^([\w]+)\.(.+)$/)
                        return targetScope[target] if not chain or chain.length isnt 3
                        return getValueChain(targetScope[chain[1]], chain[2])

                    datasource = getValueChain($scope, datasourceName)

                    throw new Error("#{datasourceName} is not a valid datasource") unless isDatasource datasource

                    rowHeight = null # this directive only works with fixed height rows.
                    viewport = null  # viewport is the parent element which contains the scrolled vieweport
                    padding = null   # padding is a function which creates padding element of a certain size
                    isLoading = false # whether we are fetching data

                    # Buffer is a sparse array containing list of rows that are already instanciated into dom
                    # or padding. padding have the class .padding, and potencially following buffer elements are
                    # sparsed out.
                    buffer = []

                    # Calling linker is the only way I found to get access to the tag name of the template
                    # to prevent the directive scope from pollution a new scope is created and destroyed
                    # right after the repeaterHandler creation is completed
                    tempScope = $scope.$new()
                    linker tempScope, (template) ->
                        repeaterType = template[0].localName
                        viewport = controllers[0].viewport
                        viewport.css({'overflow-y': 'auto', 'display': 'block'})
                        rowHeight = template.height()
                        padding = (height) ->
                            result = angular.element("<#{repeaterType} class='padding'></#{repeaterType}>")
                            result.height(height * rowHeight)
                            result

                        tempScope.$destroy()

                    # init with 1 row 0 size padding
                    buffer[0] = padding(0)
                    element.after(buffer[0])

                    viewportScope = viewport.scope() || $rootScope

                    if angular.isDefined ($attr.isLoading)
                        loading = (value) ->
                            isLoading = value
                            viewportScope[$attr.isLoading] = value
                            datasource.loading(value) if datasource.loading
                    else
                        loading = (value) ->
                            isLoading = value
                            datasource.loading(value) if datasource.loading

                    insertItem = (beforePos, pos, item) ->
                        # dont overwritte already loaded dom
                        if buffer[pos]? and not buffer[pos].hasClass('padding')
                            return

                        itemScope = $scope.$new()
                        itemScope[itemName] = item
                        itemScope.$index = pos
                        linker itemScope, (clone) ->
                            afterPadding = 0
                            if buffer[beforePos].hasClass('padding')
                                afterPadding = Math.floor(buffer[beforePos].height() / rowHeight)
                                afterPadding -= (pos - beforePos + 1)
                                buffer[beforePos].height((pos - beforePos) * rowHeight)

                            buffer[beforePos].after(clone)
                            if beforePos == pos
                                buffer[pos].remove()
                                buffer[pos] = undefined

                            # push after padding next line or deleted it
                            if buffer[pos]?
                                if buffer[pos + 1]? or (pos + 1 == buffer.length)
                                    buffer[pos].remove()
                                else
                                    buffer[pos].height(buffer[pos].height() - rowHeight)
                                    buffer[pos + 1] = buffer[pos]
                            else if pos < buffer.length - 1 and not buffer[pos + 1]?
                                buffer[pos + 1] = padding(afterPadding)
                                clone.after(buffer[pos + 1])
                            buffer[pos] = clone

                    # calculate what rows to load given the scroll viewport
                    updateView = ->
                        topIndex = Math.floor(viewport.scrollTop() / rowHeight)
                        numIndex = Math.floor(viewport.outerHeight() / rowHeight)
                        topIndex -= numIndex
                        endIndex  = topIndex + numIndex * 3
                        if topIndex > buffer.length - 1
                            topIndex = buffer.length - 1
                        if topIndex < 0
                            topIndex = 0
                        if endIndex > buffer.length
                            endIndex = buffer.length
                        loadView(topIndex, endIndex)

                    # load some lines to the DOM using the data source, making sure it is not already loaded
                    loadView = (topIndex, endIndex) ->
                        fetched = (b) -> not b.hasClass("padding")
                        while buffer[topIndex]? && fetched(buffer[topIndex]) && topIndex < endIndex
                            topIndex++

                        while buffer[endIndex - 1]? && fetched(buffer[endIndex - 1 ]) && topIndex < endIndex
                            endIndex--

                        if topIndex == endIndex # all is loaded
                            return

                        loading(true)

                        previousElemIndex = findElement(topIndex)
                        datasource.get(topIndex, endIndex - topIndex).then (d) ->
                            loading(false)
                            savedScroll = viewport.scrollTop()
                            for item in d
                                insertItem(previousElemIndex, topIndex, item)
                                previousElemIndex = topIndex
                                topIndex++

                            # as we are manipulating the DOM, the scrollTop is updated to try to follow
                            # the visible, so we must restore it after DOM manipulation
                            viewport.scrollTop(savedScroll)
                            $timeout -> maybeUpdateView()

                    # find an element in the buffer, skipping undefined directly to padding element
                    # representing this element
                    findElement = (i) ->
                        while i > 0
                            if buffer[i]?
                                return i
                            i--
                        0

                    # Create padding in the end of the buffer
                    updateTotalSize = (newSize) ->
                        if newSize > buffer.length
                            lastElementIndex = findElement(buffer.length - 1)
                            lastElement = buffer[lastElementIndex]
                            if lastElement.hasClass("padding")
                                lastElement.height((newSize - lastElementIndex) * rowHeight)
                            buffer[newSize - 1] = undefined

                            $timeout -> maybeUpdateView()

                    maybeUpdateView = ->
                        if !$rootScope.$$phase && !isLoading
                            $timeout(updateView)

                    setScrollPosition = (pos) ->
                        $timeout ->
                            viewport.scrollTop(pos * rowHeight)
                            maybeUpdateView()
                        , 100


                    $(window).bind 'resize', maybeUpdateView
                    viewport.bind 'scroll', maybeUpdateView

                    $scope.$watch $attr.totalSize, (n) ->
                        updateTotalSize(n)

                    $scope.$watch $attr.scrollPosition, (n, o) ->
                        if n?
                            setScrollPosition(n)

                    $scope.$on '$destroy', ->
                        $(window).unbind 'resize', maybeUpdateView
                        viewport.unbind 'scroll', maybeUpdateView


        }
