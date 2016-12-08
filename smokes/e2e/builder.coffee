# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class builderPage
    constructor: (builder, forcename) ->
        @builderID = {
            "runtest" : 1
            "slowruntest": 2
        }[builder]
        @forceName=forcename

    goDefault: ->
        browser.get('#/builders')

    go: () ->
        browser.get('#/builders/#{@builderID}/')

    goForce: (forcename) ->
        browser.get("#/builders/#{@builderID}/force/#{@forceName}")

    getBuildCount: () ->
        return element.all(By.css('span.badge-status.results_SUCCESS')).count()

    waitNextBuildFinished: (reference) ->
        self = this
        buildCountIncrement = () ->
            self.getBuildCount().then (currentBuildCount) ->
                return +currentBuildCount == +reference + 1
        browser.wait(buildCountIncrement, 2000)

module.exports = builderPage
