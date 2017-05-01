# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

BasePage = require("./base.coffee")

class ConsolePage extends BasePage
    constructor: ->

    go: ->
        browser.get('#/console')
    countSuccess: () ->
        element.all(By.css('.badge-status.results_SUCCESS')).count()

module.exports = ConsolePage
