# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class waterfallPage
    constructor: (builder) ->
        @builder = builder

    go: () ->
        browser.get('#/waterfall')

    checkBuilder: (hrefBuilder) ->
        browser.getLocationAbsUrl().then (localURL) ->
            split = hrefBuilder[0].split('#')
            expect(split[split.length-1]).toContain(localURL)

    checkBuildResult: () ->
        popupContents = element.all(By.css('a.ng-binding')).first()
        popupContents.getAttribute('href').then (linkTarget) ->
            popupContents.click()
            browser.getLocationAbsUrl().then (buildUrl) ->
                split = linkTarget.split('#')
                expect(split[split.length-1]).toContain(buildUrl)

    goBuild: () ->
        buildList = element.all(By.css('text.id')).last()
        buildList.click()

    goBuildAndClose: () ->
        self =  this
        self.goBuild()
        popupClose = element.all(By.css('i.fa-times'))
        popupClose.click()
        expect(element.all(By.css('modal-dialog')).isPresent).toBe(undefined)

    goBuildAndCheck: () ->
        self =  this
        self.goBuild()
        self.checkBuildResult()

    goBuilderAndCheck: (builderRef) ->
        self = this
        localBuilder = element.all(By.linkText(@builder))
        localBuilder.getAttribute('href').then (str) ->
            localBuilder.click()
            self.checkBuilder(str)

module.exports = waterfallPage
