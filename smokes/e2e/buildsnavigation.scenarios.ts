// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { HomePage } from './pages/home';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

describe('previousnextlink', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('runtests', 'force');
        return force =  new ForcePage();
    });
    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('has afterEach working', function() {
    });

    it('should navigate in the builds history by using the previous next links', async () => {
        await builder.go();
        const lastbuild = await builder.getLastSuccessBuildNumber();
        // Build #1
        await builder.goForce();
        let startButton = force.getStartButton();
        await browser.wait(EC.elementToBeClickable(startButton),
                           5000,
                           "start button not clickable");
        await startButton.click();
        await builder.go();
        await builder.waitNextBuildFinished(lastbuild);
        // Build #2
        await builder.goForce();
        startButton = force.getStartButton();
        await browser.wait(EC.elementToBeClickable(startButton),
                           5000,
                           "start button not clickable");
        await startButton.click();
        await builder.go();
        await builder.waitNextBuildFinished(+lastbuild + 1);
        await builder.goBuild(+lastbuild + 2);
        const lastBuildURL = await browser.getCurrentUrl();
        let previousButton = builder.getPreviousButton();
        await browser.wait(EC.elementToBeClickable(previousButton),
                           5000,
                           "previous button not clickable");
        await previousButton.click()
        expect(await browser.getCurrentUrl()).not.toMatch(lastBuildURL);
        let nextButton = builder.getNextButton();
        await browser.wait(EC.elementToBeClickable(nextButton),
                           5000,
                           "next button not clickable");
        await nextButton.click();
        expect(await browser.getCurrentUrl()).toMatch(lastBuildURL);
    });
});

describe('forceandstop', function() {
    let force = null;
    let builder = null;

    beforeEach(function() {
        builder = new BuilderPage('slowruntests', 'force');
        force =  new ForcePage();
    });

    it('should create a build with a dedicated reason and stop it during execution', async () => {

        await builder.goForce();
        let startButton = force.getStartButton();
        await browser.wait(EC.elementToBeClickable(startButton),
                           5000,
                           "start button not clickable");
        await startButton.click();
        expect(await browser.getCurrentUrl()).toMatch("/builders/\[1-9]/builds/\[1-9]");
        let stopButton = builder.getStopButton();
        await browser.wait(EC.elementToBeClickable(stopButton),
                           5000,
                           "stop button not clickable");
        await stopButton.click();
    });
});
