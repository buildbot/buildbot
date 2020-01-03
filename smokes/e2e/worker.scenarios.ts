// test goal: checks the capability to navigate on about web page
// to use previous and next link

import { WorkerPage } from './pages/worker';
import { SettingsPage } from './pages/settings';

describe('worker', function() {
    let worker = null;
    let builder = null;
    let settings = null;

    beforeEach(function() {
        worker = new WorkerPage('runtests');
        settings = new SettingsPage('runtests');
    });

    const navigateAndCheckBuilderLink = async (builderName) => {
        await settings.goSettings();
        await settings.changeShowWorkerBuilders(true);
        await settings.checkShowWorkerBuilders(true);
        await worker.goWorker();
        await worker.checkWorkerPage();
        await worker.checkHrefPresent();
        builder = await worker.goBuilderLink(builderName);
        await builder.checkBuilderURL();
    }

    it('should navigate to the worker page, check the one slowruntests link', async () => {
        await navigateAndCheckBuilderLink("slowruntests");
    });

    it('should navigate to the worker page, check the one runtests link', async () => {
        await navigateAndCheckBuilderLink("runtests");
    });
});
