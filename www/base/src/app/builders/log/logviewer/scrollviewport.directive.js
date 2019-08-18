/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
/*
based on https://github.com/Hill30/NGScroller (MIT license)

ui.scroll is a good directive for infinite scrolling. Its inner working makes it not very adapted to viewing log:

This scroll directive uses ui.scroll base, but replace the whole DOM manipulation code
- Can directly scroll to arbitrary position
- Don't remove out-of-sight DOM. Eventually this will result in huge dom, so please make sure to use bind-once childs.
    This however has the advantage on only loading each line once.
- Support line count, and adapt scroll bar appropriately
- Can follow the end of stream, via updating the scroll-position attribute
- row height is fixed (or you cannot make geometric calculation to determine the positions of arbitrary elements)

This directive uses JQuery for DOM manipulation

Performance considerations:

Having to deal with huge logs is not uncommon thing we buildbot, we need to deal with them as fast as possible.
AngularJS does a lot of things with the DOM, and is not as fast as we can do.

This is why using angularJS's linker is avoided. We rather use lodash template(), that is configured to
simulate angularjs 1.3 "bindonce" templating.

With this technic, we can load 20k lines log in 2 seconds.
*/
class ScrollViewport {
    constructor($log) {
        return {
            controller:
                [ '$scope', '$element',
                    function(scope, element) {
                        this.viewport = element;
                        return this;
                    }
                ]
        };
    }
}

class Scroll {
    constructor($log, $injector, $rootScope, $timeout, $window) {
        return {
            require: ['?^scrollViewport'],
            transclude: 'element',
            priority: 1000,
            terminal: true,
            compile(elementTemplate, attr, linker) {
                return function($scope, element, $attr, controllers) {

                    let loading;
                    const log = $log.debug || $log.log;

                    const match = $attr.scroll.match(/^\s*(\w+)\s+in\s+([\w\.]+)\s*$/);
                    if (!match) {
                        throw new Error("Expected scroll in form of '_item_ in _datasource_'"+
                            `but got '${$attr.uiScroll}'`);
                    }

                    const itemName = match[1];
                    const datasourceName = match[2];
                    const totalSize = null;

                    const isDatasource = datasource => angular.isObject(datasource) && datasource.get && angular.isFunction(datasource.get);

                    var getValueChain = function(targetScope, target) {
                        if (!targetScope) { return null; }
                        const chain = target.match(/^([\w]+)\.(.+)$/);
                        if (!chain || (chain.length !== 3)) { return targetScope[target]; }
                        return getValueChain(targetScope[chain[1]], chain[2]);
                    };

                    const datasource = getValueChain($scope, datasourceName);

                    if (!isDatasource(datasource)) { throw new Error(`${datasourceName} is not a valid datasource`); }

                    let rowHeight = null; // this directive only works with fixed height rows.
                    let viewport = null;  // viewport is the parent element which contains the scrolled vieweport
                    let padding = null;   // padding is a function which creates padding element of a certain size
                    let isLoading = false; // whether we are fetching data
                    let loadAll = false;  // should we load the whole log

                    // Buffer is a sparse array containing list of rows that are already instantiated into dom
                    // or padding. padding have the class .padding, and potentially following buffer elements are
                    // sparsed out.
                    const buffer = [];

                    // Calling linker is the only way I found to get access to the tag name of the template
                    // to prevent the directive scope from pollution a new scope is created and destroyed
                    // right after the repeaterHandler creation is completed
                    const tempScope = $scope.$new();
                    linker(tempScope, function(template) {
                        const repeaterType = template[0].localName;
                        ({ viewport } = controllers[0]);
                        viewport.css({'overflow-y': 'auto', 'display': 'block'});
                        rowHeight = template.height();

                        // Replace angularjs linker by _.template, which is much faster
                        let rowTemplate = `<${repeaterType} style='height:${rowHeight}px;'>` +
                            `${template[0].innerHTML}</${repeaterType}>`;
                        rowTemplate = _.template(rowTemplate, {interpolate: /\{\{::(.+?)\}\}/g} );
                        linker = (scope, cb) => cb(angular.element(rowTemplate(scope)));


                        padding = function(height) {
                            const result = angular.element(`<${repeaterType} class='padding'></${repeaterType}>`);
                            result.set_height = function(height) {
                                // we use _height as a cache that holds the height of the padding
                                // using jquery.height() is terribly slow, as it internally re-style the item
                                result._height = height;
                                if (!result._height_changing) {
                                    $timeout(function() {
                                        result.height(result._height * rowHeight);
                                        result._height_changing = false;
                                    });
                                }
                                return result._height_changing = true;
                            };
                            result.set_height(height);
                            return result;
                        };

                        return tempScope.$destroy();
                    });

                    // init with 1 row 0 size padding
                    buffer[0] = padding(0,0);
                    const parent = angular.element("<div>");
                    element.after(parent);
                    parent.append(buffer[0]);

                    const viewportScope = viewport.scope() || $rootScope;

                    if (angular.isDefined(($attr.isLoading))) {
                        loading = function(value) {
                            isLoading = value;
                            viewportScope[$attr.isLoading] = isLoading;
                            if (datasource.loading) { return datasource.loading(value); }
                        };
                    } else {
                        loading = function(value) {
                            isLoading = value;
                            if (datasource.loading) { return datasource.loading(value); }
                        };
                    }

                    const insertItem = function(beforePos, pos, item) {
                        // don't overwritte already loaded dom
                        if ((buffer[pos] != null) && (buffer[pos]._height == null)) {
                            return;
                        }

                        const itemScope = {};
                        itemScope[itemName] = item;
                        itemScope.$index = pos;
                        return linker(itemScope, function(clone) {
                            let afterPadding = 0;
                            if (buffer[beforePos]._height != null) {
                                afterPadding = buffer[beforePos]._height;
                                afterPadding -= ((pos - beforePos) + 1);
                                buffer[beforePos].set_height(pos - beforePos);
                            }

                            buffer[beforePos].after(clone);
                            if (beforePos === pos) {
                                buffer[pos].remove();
                                buffer[pos] = undefined;
                            }

                            // push after padding next line or deleted it
                            if (buffer[pos] != null) {
                                if ((buffer[pos + 1] != null) || ((pos + 1) === buffer.length)) {
                                    buffer[pos].remove();
                                } else {
                                    buffer[pos].set_height(buffer[pos]._height - 1);
                                    buffer[pos + 1] = buffer[pos];
                                }
                            } else if ((pos < (buffer.length - 1)) && (buffer[pos + 1] == null)) {
                                buffer[pos + 1] = padding(afterPadding);
                                clone.after(buffer[pos + 1]);
                            }
                            return buffer[pos] = clone;
                        });
                    };

                    // calculate what rows to load given the scroll viewport
                    const updateView = function() {
                        let endIndex, topIndex;
                        if (loadAll) {
                            topIndex = 0;
                            endIndex = buffer.length;
                        } else {
                            topIndex = Math.floor(viewport.scrollTop() / rowHeight);
                            const numIndex = Math.floor(viewport.outerHeight() / rowHeight);
                            topIndex -= numIndex;
                            endIndex  = topIndex + (numIndex * 3);
                            if (topIndex > (buffer.length - 1)) {
                                topIndex = buffer.length - 1;
                            }
                            if (topIndex < 0) {
                                topIndex = 0;
                            }
                            if (endIndex > buffer.length) {
                                endIndex = buffer.length;
                            }
                        }
                        loadView(topIndex, endIndex);
                    };

                    // load some lines to the DOM using the data source, making sure it is not already loaded
                    var loadView = function(topIndex, endIndex) {
                        const fetched = b => b._height == null;
                        if (isLoading) {
                            return;
                        }
                        while ((buffer[topIndex] != null) && fetched(buffer[topIndex]) && (topIndex < endIndex)) {
                            topIndex++;
                        }

                        while ((buffer[endIndex - 1] != null) && fetched(buffer[endIndex - 1 ]) && (topIndex < endIndex)) {
                            endIndex--;
                        }

                        if (topIndex === endIndex) { // all is loaded
                            return;
                        }
                        loading(true);

                        let previousElemIndex = findElement(topIndex);
                        datasource.get(topIndex, endIndex - topIndex).then(function(d) {
                            loading(false);
                            for (let item of Array.from(d)) {
                                insertItem(previousElemIndex, topIndex, item);
                                previousElemIndex = topIndex;
                                topIndex++;
                            }

                            $timeout(() => maybeUpdateView());
                        });
                    };

                    // find an element in the buffer, skipping undefined directly to padding element
                    // representing this element
                    var findElement = function(i) {
                        while (i > 0) {
                            if (buffer[i] != null) {
                                return i;
                            }
                            i--;
                        }
                        return 0;
                    };

                    // Create padding in the end of the buffer
                    const updateTotalSize = function(newSize) {
                        if (newSize > buffer.length) {
                            const lastElementIndex = findElement(buffer.length - 1);
                            const lastElement = buffer[lastElementIndex];
                            parent.height(newSize*rowHeight);
                            buffer[newSize - 1] = undefined;
                            if (lastElement._height != null) {
                                lastElement.set_height(newSize - lastElementIndex);
                            }

                            return $timeout(() => maybeUpdateView());
                        }
                    };

                    var maybeUpdateView = function() {
                        if (!$rootScope.$$phase && !isLoading) {
                            return $timeout(updateView);
                        }
                    };

                    const setScrollPosition = pos =>
                        $timeout(function() {
                            viewport.scrollTop(pos * rowHeight);
                            return maybeUpdateView();
                        }
                        , 100)
                    ;


                    $(window).bind('resize', maybeUpdateView);
                    viewport.bind('scroll', maybeUpdateView);

                    $scope.$watch($attr.totalSize, n => updateTotalSize(n));

                    $scope.$watch($attr.scrollPosition, function(n) {
                        if (n != null) {
                            setScrollPosition(n);
                        }
                    });

                    $scope.$watch($attr.loadAll, function(n) {
                        if (n) {
                            loadAll = true;
                            $timeout(maybeUpdateView);
                        }
                    });

                    $scope.$on('$destroy', function() {
                        $(window).unbind('resize', maybeUpdateView);
                        viewport.unbind('scroll', maybeUpdateView);
                    });
                };
            }


        };
    }
}


angular.module('app')
.directive('scrollViewport', ['$log', ScrollViewport])
.directive('scroll', ['$log', '$injector', '$rootScope', '$timeout', '$window', Scroll]);
