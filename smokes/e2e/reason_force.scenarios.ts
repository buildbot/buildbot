// test goal: checks the capability to define a reason and to cancel/start the build

import { HomePage } from './pages/home';
import { BuilderPage } from './pages/builder';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from './utils';

describe('force and cancel', function() {
    let builder = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        await builder.goBuildersList();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should create a build', async () => {
        await builder.go();
        let lastbuild = await builder.getLastFinishedBuildNumber();
        let force = await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitBuildFinished(lastbuild + 1);
    });

    it('should create a build with a dedicated reason and cancel it', async () => {
        await builder.go();
        let force = await builder.goForce();
        let cancelButton = force.getCancelButton();
        await bbrowser.wait(EC.elementToBeClickable(cancelButton),
                            "cancel button not clickable");
        await cancelButton.click();
    });

    it('should create a build with a dedicated reason and Start it', async () => {
        await builder.go();
        let force = await builder.goForce();
        await force.setReason("New Test Reason");
        await force.setYourName("user@example.com");
        await force.setProjectName("BBOT9");
        await force.setBranchName("Gerrit Branch");
        await force.setRepo("http//name.com");
        await force.setRevisionName("12345");
        await force.clickStartButtonAndWaitRedirectToBuild();
    });
});
