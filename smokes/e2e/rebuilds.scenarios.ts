// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { HomePage } from './pages/home';
import { ForcePage } from './pages/force';
import { BuilderPage } from './pages/builder';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

describe('rebuilds', function() {
    let force = null;
    let builder = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        force =  new ForcePage();
        await builder.goBuildersList();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should navigate to a dedicated build and to use the rebuild button', async () => {
        await builder.go();
        const lastbuild: number = await builder.getLastFinishedBuildNumber();
        await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitBuildFinished(lastbuild + 1);
        await builder.goBuild(lastbuild + 1);
        await browser.getCurrentUrl();
        let rebuildButton = builder.getRebuildButton();
        await browser.wait(EC.elementToBeClickable(rebuildButton),
                           5000,
                           "rebuild button not clickable");
        await rebuildButton.click();
        await builder.waitGoToBuild(lastbuild + 2);
    });
});
