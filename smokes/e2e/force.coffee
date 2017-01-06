# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class forcePage
    constructor: ->
        browser.get('#/builders')

    setInputText: (cssLabel, value) ->
        setInputValue = element(By.css("forcefield label[for=#{cssLabel}] + div input"))
        setInputValue.clear()
        setInputValue.sendKeys(value)
        expect(setInputValue.getAttribute('value')).toBe(value)

    setReason: (reason) ->
        return @setInputText("reason", reason)

    setYourName: (yourName) ->
        return @setInputText("username", yourName)

    setProjectName: (projectName) ->
        return @setInputText("project", projectName)

    setBranchName: (branchName) ->
        return @setInputText("branch", branchName)

    setRepo: (repo) ->
        return @setInputText("repository", repo)

    setRevisionName: (RevisionName) ->
        return @setInputText("revision", RevisionName)

    getStartButton: ->
        return element(By.buttonText('Start Build'))

    getCancelButton: ->
        return element(By.buttonText('Cancel'))

    getCancelWholeQueue: ->
        return element(By.buttonText('Cancel Whole Queue'))

    getStopButton: ->
        return element(By.buttonText('Stop'))

module.exports = forcePage
