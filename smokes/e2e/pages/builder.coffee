# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

BasePage = require("./base.coffee")

class BuilderPage extends BasePage
    constructor: (@builder, forcename) ->
        @forceName=forcename

    goDefault: ->
        browser.get('#/builders')

    go: () ->
        browser.get('#/builders')
        localBuilder = element.all(By.linkText(@builder))
        localBuilder.click()

    goForce: () ->
        @go()
        element.all(By.buttonText(@forceName)).first().click()

    goBuild: (buildRef) ->
        @go()
        element.all(By.linkText(buildRef.toString())).click()

    getLastSuccessBuildNumber: () ->
        element.all(By.css('span.badge-status.results_SUCCESS')).then (elements)->
            if elements.length == 0
                return 0
            return elements[0].getText().then (numberstr) ->
                return +numberstr

    waitNextBuildFinished: (reference) ->
        self = this
        buildCountIncrement = () ->
            self.getLastSuccessBuildNumber().then (currentBuildCount) ->
                return currentBuildCount == reference + 1
        browser.wait(buildCountIncrement, 20000)

    waitGoToBuild: (expected_buildnumber) ->
        isInBuild = () ->
            browser.getCurrentUrl().then (buildUrl) ->
                split = buildUrl.split("/")
                builds_part = split[split.length-2]
                number = +split[split.length-1]
                if builds_part != "builds"
                    return false
                if number != expected_buildnumber
                    return false
                return true
        browser.wait(isInBuild, 20000)

    getStopButton: ->
        return element(By.buttonText('Stop'))

    getPreviousButton: ->
        element(By.partialLinkText('Previous'))

    getNextButton: ->
        element(By.partialLinkText('Next'))

    getRebuildButton: ->
        return element(By.buttonText('Rebuild'))

    checkBuilderURL: () ->
        builderLink = element.all(By.linkText(@builder))
        expect(builderLink.count()).toBeGreaterThan(0)

module.exports = BuilderPage
