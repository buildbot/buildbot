# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class builderPage
    constructor: (@builder, forcename) ->
        @forceName=forcename

    goDefault: ->
        browser.get('#/builders')

    go: () ->
        browser.get('#/builders')
        element.all(By.partialLinkText(@builder)).first().click()

    goForce: (forcename) ->
        browser.get('#/builders')
        element.all(By.partialLinkText(@builder)).first().click()
        element.all(By.buttonText(@forceName)).first().click()

    getLastSuccessBuildNumber: () ->
        element.all(By.css('span.badge-status.results_SUCCESS')).then (elements)->
            if elements.length == 0
                return 0
            return elements[0].getText()

    waitNextBuildFinished: (reference) ->
        self = this
        buildCountIncrement = () ->
            self.getLastSuccessBuildNumber().then (currentBuildCount) ->
                return +currentBuildCount == +reference + 1
        browser.wait(buildCountIncrement, 10000)

module.exports = builderPage
