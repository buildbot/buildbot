# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class waterfallPage
    constructor: (builder) ->
        @builder = builder

    go: () ->
        browser.get('#/waterfall')

    checkBuilder: () ->
        browser.getCurrentUrl().then (currentUrl) ->
            expect(currentUrl).toContain("builders/")

    checkBuildResult: () ->
        popupContents = element.all(By.css('a.ng-binding')).first()
        popupContents.getAttribute('href').then (linkTarget) ->
            popupContents.click()
            expect(browser.getCurrentUrl()).toEqual(linkTarget)

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

    clickWhenClickable: (element) ->
        browser.wait ->
            element.click().then (->
                true
            ), ->
                console.log 'not clickable'
                false

    goBuilderAndCheck: (builderRef) ->
        self = this
        localBuilder = element.all(By.linkText(@builder))
        clickWhenClickable(localBuilder)
        self.checkBuilder()

module.exports = waterfallPage
