# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

BasePage = require("./base.coffee")

class WaterfallPage extends BasePage
    constructor: (builder) ->
        @builder = builder

    go: () ->
        browser.get('#/waterfall')

    checkBuilder: () ->
        browser.getCurrentUrl().then (currentUrl) ->
            expect(currentUrl).toContain("builders/")

    checkBuildResult: () ->
        firstLinkInPopup = element.all(By.css('.modal-dialog a')).first()
        firstLinkInPopup.click()
        browser.getCurrentUrl().then (currentUrl) ->
            expect(currentUrl).toContain("builders/")
            expect(currentUrl).toContain("builds/")

    goBuild: () ->
        buildList = element.all(By.css('text.id')).last()
        buildList.click()

    goBuildAndClose: () ->
        self =  this
        self.goBuild()
        popupClose = element.all(By.css('i.fa-times'))
        popupClose.click()
        expect($('modal-dialog').isPresent()).toBeFalsy()

    goBuildAndCheck: () ->
        self =  this
        self.goBuild()
        self.checkBuildResult()

    goBuilderAndCheck: (builderRef) ->
        self = this
        localBuilder = element.all(By.linkText(@builder))
        @clickWhenClickable(localBuilder)
        self.checkBuilder()

module.exports = WaterfallPage
