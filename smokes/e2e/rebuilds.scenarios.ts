// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link


import { HomePage } from './pages/home';
import { BuilderPage } from './pages/builder';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from './utils';

describe('rebuilds', function() {
    let builder = null;

    beforeEach(async () => {
        builder = new BuilderPage('runtests', 'force');
        await builder.goBuildersList();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('should navigate to a dedicated build and to use the rebuild button', async () => {
        await builder.go();
        const lastbuild: number = await builder.getLastFinishedBuildNumber();
        let force = await builder.goForce();
        await force.clickStartButtonAndWaitRedirectToBuild();
        await builder.go();
        await builder.waitBuildFinished(lastbuild + 1);
        await builder.goBuild(lastbuild + 1);
        await browser.getCurrentUrl();
        let rebuildButton = builder.getRebuildButton();
        await bbrowser.wait(EC.elementToBeClickable(rebuildButton),
                            "rebuild button not clickable");
        await rebuildButton.click();
        await builder.waitGoToBuild(lastbuild + 2);
    });
});
