// test goal: checks the capability to navigate on about web page
// to use previous and next link

import { WorkerPage } from './pages/worker';
import { SettingsPage } from './pages/settings';

describe('', function() {
    let worker = null;
    let builder = null;
    let settings = null;

    beforeEach(function() {
        worker = new WorkerPage('runtests');
        settings = new SettingsPage('runtests');
    });

    describe('check worker page', () =>
        it('should navigate to the worker page, check the one builder inside', async () => {
            await settings.goSettings();
            await settings.changeShowWorkerBuilders(true);
            await settings.checkShowWorkerBuilders(true);
            await worker.goWorker();
            await worker.checkWorkerPage();
            await worker.checkHrefPresent();
            builder = await worker.goBuilderLink('slowruntests');
            await builder.checkBuilderURL();
        })
    );

    describe('check worker page', () =>
        it('should navigate to the worker page, check the one builder inside', async () => {
            await settings.goSettings();
            await settings.changeShowWorkerBuilders(true);
            await settings.checkShowWorkerBuilders(true);
            await worker.goWorker();
            await worker.checkWorkerPage();
            await worker.checkHrefPresent();
            builder = await worker.goBuilderLink('runtests');
            await builder.checkBuilderURL();
        })
    );

});
