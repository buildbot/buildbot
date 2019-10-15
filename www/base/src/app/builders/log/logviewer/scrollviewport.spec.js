/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS202: Simplify dynamic range loops
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('page with sidebar', function() {
    let queries, rootScope, scope, timeout;
    beforeEach(angular.mock.module("app"));
    let elmBody = (scope = (rootScope = (queries = (timeout = null))));
    let elmContent = null;
    const padding = pix => ({type: "padding", height: pix});
    const elements = (start, end) => ({type: "elements", start, end});

    const assertDOM = function(l) {
        const childs = [];
        $("div", elmContent).each((i, c) => childs.push(c));

        for (var item of Array.from(l)) {
            var c;
            if (item.type === "padding") {
                c = childs.shift();
                expect($(c).hasClass("padding")).toBe(true, c.outerHTML);
                expect($(c).height()).toEqual(item.height, c.outerHTML);
            }
            if (item.type === "elements") {
                for (let i = item.start, { end } = item, asc = item.start <= end; asc ? i <= end : i >= end; asc ? i++ : i--) {
                    c = childs.shift();
                    expect($(c).hasClass("padding")).toBe(false, c.outerHTML);
                    expect(c.innerText).toEqual(i.toString() + "a" + i.toString(), c.outerHTML);
                }
            }
        }
    };
    const printDOM = () =>
        $("div", elmContent).each(function() {
            if ($(this).hasClass("padding")) {
                return console.log("padding", $(this).height());
            } else {
                return console.log("row", this.innerText, $(this).height());
            }
        })
    ;

    const scrollTo = function(pos, verifyPos) {
        if (verifyPos == null) { verifyPos = pos; }
        // we scroll pos
        elmBody.scrollTop(pos);
        // make sure that worked
        expect(elmBody.scrollTop()).toBe(verifyPos);

        // as the scroll is automatic, we need to force the event
        elmBody.trigger("scroll");

        timeout.flush();
        // make sure it did not changed
        expect(elmBody.scrollTop()).toBe(verifyPos);
    };

    beforeEach(inject(function($rootScope, $compile, glMenuService, $timeout, $q, $document) {
        timeout = $timeout;
        queries = [];
        rootScope = $rootScope;
        elmBody = angular.element(
            '<div scroll-viewport style="height:50px">'+
            '<div style="height:10px" total-size="1000" scroll="item in items">{{::$index}}a{{::item.v}}'+
            '</div></div>'
        );
        scope = $rootScope.$new();

        scope.items = {
            get(index, num) {
                queries.push([index, num]);
                const d = $q.defer();
                $timeout(function() {
                    const ret = [];
                    for (let i = 0, end = num - 1, asc = 0 <= end; asc ? i <= end : i >= end; asc ? i++ : i--) { ret.push({v: (index + i)}); }
                    d.resolve(ret);
                });
                return d.promise;
            }
        };
        $compile(elmBody)(scope)[0];
        scope.$digest();

        // we need to append to body, so that the element is styled properly, and gets a height
        elmBody.appendTo("body");
        elmContent = $("div", elmBody)[0];}));

    // ViewPort height is 50, and item height is 10, so a screen should contain 5 item
    it('should initially load 2 screens', inject(function($timeout) {
        $timeout.flush();
        expect(queries).toEqual([[0,10]]);
        assertDOM([
            elements(0,9),
            padding(9900)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);
    })
    );

    it('if scroll to middle, should load 3 screens', inject(function($timeout) {
        // initial load
        $timeout.flush();

        scrollTo(600);

        expect(queries).toEqual([[0,10], [55, 15]]);
        assertDOM([
            elements(0,9),   // 100
            padding(450),    // 550
            elements(55,69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);
    })
    );

    it('several scroll loads several screens, and paddings are cleaned out',
       inject(function($timeout) {
        // initial load
        $timeout.flush();

        scrollTo(600);
        expect(queries).toEqual([[0,10], [55, 15]]);
        assertDOM([
            elements(0,9),   // 100
            padding(450),    // 550
            elements(55,69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);

        scrollTo(400);
        expect(queries).toEqual([[0,10], [55, 15], [35, 15]]);
        assertDOM([
            elements(0,9),   // 100
            padding(250),    // 350
            elements(35,49), // 500
            padding(50),    // 550
            elements(55,69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);

        scrollTo(500);
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5]]);
        assertDOM([
            elements(0,9),   // 100
            padding(250),    // 350
            elements(35, 69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);

        scrollTo(100);
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10]]);
        assertDOM([
            elements(0,19),   // 200
            padding(150),    // 350
            elements(35, 69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);

        scrollTo(200);
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10], [20, 10]]);
        assertDOM([
            elements(0,29),   // 300
            padding(50),      // 350
            elements(35, 69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);

        scrollTo(300);
        expect(queries).toEqual([[0,10], [55, 15], [35, 15], [50, 5], [10, 10], [20, 10], [30, 5]]);
        assertDOM([
            elements(0,69), // 700
            padding(10000 - 700)
        ]);
        expect(elmBody[0].scrollHeight).toEqual(1000 * 10);
    })
    );

    it('Scroll to the end', inject(function($timeout) {
        // initial load
        $timeout.flush();
        scrollTo(10000, 9950);

        expect(queries).toEqual([[0,10], [990, 10]]);
        assertDOM([
            elements(0,9),   // 100
            padding(9800),   // 9900
            elements(990, 999) // 10000
        ]);}));
});
