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
        return settings = new SettingsPage('runtests');
    });

    describe('check worker page', () =>
        it('should navigate to the worker page, check the one builder inside', function() {
            settings.goSettings();
            settings.changeShowWorkerBuilders(true);
            settings.checkShowWorkerBuilders(true);
            worker.goWorker();
            worker.checkWorkerPage();
            worker.checkHrefPresent();
            builder = worker.goBuilderLink('slowruntests');
            builder.checkBuilderURL();
        })
    );

    describe('check worker page', () =>
        it('should navigate to the worker page, check the one builder inside', function() {
            settings.goSettings();
            settings.changeShowWorkerBuilders(true);
            settings.checkShowWorkerBuilders(true);
            worker.goWorker();
            worker.checkWorkerPage();
            worker.checkHrefPresent();
            builder = worker.goBuilderLink('runtests');
            builder.checkBuilderURL();
    })
);

});
