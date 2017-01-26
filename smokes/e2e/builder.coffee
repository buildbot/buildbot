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
        browser.wait(buildCountIncrement, 10000)

    waitGoToBuild: (expected_buildnumber) ->
        isInBuild = () ->
            browser.getLocationAbsUrl().then (buildUrl) ->
                split = buildUrl.split("/")
                builds_part = split[split.length-2]
                number = +split[split.length-1]
                if builds_part != "builds"
                    return false
                if number != expected_buildnumber
                    return false
                return true
        browser.wait(isInBuild, 10000)

    getStopButton: ->
        return element(By.buttonText('Stop'))

    getPreviousButton: ->
        element(By.partialLinkText('Previous'))

    getNextButton: ->
        element(By.partialLinkText('Next'))

    getRebuildButton: ->
        return element(By.buttonText('Rebuild'))

module.exports = builderPage
