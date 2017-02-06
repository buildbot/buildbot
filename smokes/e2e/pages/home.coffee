# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class HomePage
    #constructor: (@builder)->
    constructor: ()->

    go: () ->
        browser.get('#/')

    getPanel: () ->
        return element.all(By.css(".panel-title"))

    waitAllBuildsFinished: () ->
        @go()
        self = this
        noRunningBuilds = () ->
            element.all(By.css("h4")).getText().then (text) ->
                text = text.join(" ")
                return text.toLowerCase().indexOf("0 build running") >= 0
        browser.wait(noRunningBuilds, 10000)

module.exports = HomePage
