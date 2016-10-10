# coffee script 
# test goal: checks the capability to define a reason and to cancel/start the build

forceSchedulerPage = require('./reason_force.coffee')

describe('', () ->
    beforeEach(() ->
        reasonForce =  new forceSchedulerPage()
        reasonForce.get()
    )
)

describe 'reasoncancel', () ->
    it 'should create a build with a dedicated reason and cancel it', () ->

        reasonForce =  new forceSchedulerPage()
        reasonForce.getLink('1/')
        currentURL0 = browser.getCurrentUrl()
        currentURL0.then (v) -> console.log v
        reasonForce.getLink('1/force')
        currentURL1 = browser.getCurrentUrl()
        currentURL1.then (v) -> console.log(v)
        reasonForce.getLink('1/force/force')
        reasonForce.findReasonCSS("New Test Reason")
        reasonForce.findYourName("FaceLess User")
        reasonForce.findProjectName("BBOT9")
        reasonForce.findBranchName("Gerrit Branch")
        reasonForce.findRepo("http//name.com")
        reasonForce.findRevisionName("12345")
        reasonForce.getCancel

        
describe 'reasonstart', () ->
    it 'should create a build with a dedicated reason and Start it', () ->

        reasonForce =  new forceSchedulerPage()
        reasonForce.getLink('1/')
        currentURL0 = browser.getCurrentUrl()
        currentURL0.then (v) -> console.log v
        reasonForce.getLink('1/force')
        currentURL1 = browser.getCurrentUrl()
        currentURL1.then (v) -> console.log(v)
        reasonForce.getLink('1/force/force')
        reasonForce.findReasonCSS("New Test Reason")
        reasonForce.getStart


