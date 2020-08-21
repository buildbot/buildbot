// test goal: checks the capability to navigate in a dedicated build
// to use previous and next link

import { HomePage } from './pages/home';
import { PendingBuildrequestsPage } from './pages/pendingbuildrequests';
import { BuilderPage } from './pages/builder';
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from './utils';

describe('pending build requests', function() {
    let builder = null;
    let pendingBuildrequests = null;

    beforeEach(async () => {
        builder = new BuilderPage('slowruntests', 'force');
        pendingBuildrequests = new PendingBuildrequestsPage();
        await builder.goBuildersList();
    });

    afterEach(async () => {
        const homePage = new HomePage();
        await homePage.waitAllBuildsFinished();
    });

    it('shows', async () => {
        let force = await builder.goForce();
        await force.clickStartButton();
        await builder.goForce();
        await force.clickStartButton();

        // hopefully we'll see at least one buildrequest by the time we get to
        // the pending build requests page
        await pendingBuildrequests.go();

        const isBulidrequestsVisible = async () => {
            let count = await pendingBuildrequests.getAllBuildrequestRows().count();
            return count > 0;
        };
        await bbrowser.wait(isBulidrequestsVisible,
                            "did not find buildrequests");

        const br = pendingBuildrequests.getAllBuildrequestRows().first();
        expect(await br.element(By.css('td:nth-child(2) a')).getText()).toMatch('slowruntests');

        // kill remaining builds
        await builder.go();
        await force.clickCancelWholeQueue();

        await bbrowser.wait(EC.alertIsPresent(),
                            "did not find confirmation alert");
        await browser.switchTo().alert().accept();
    });
});
