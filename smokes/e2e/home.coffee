# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class HomePage
    #constructor: (@builder)->
    constructor: ()->
        browser.get('#/')

    go: () ->
        browser.get('#/')

    getPanel: () ->
        return element.all(By.css(".panel-title"))

module.exports = HomePage
