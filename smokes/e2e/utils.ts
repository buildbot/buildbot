// this defines a wrapper for protractor.browser which intercepts various calls from the tests
// and adds additional logging. This allows much better understanding of test failures without
// trying to debug the tests themselves

import { browser } from 'protractor';

export class BBBrowser {

    static defaultTimeoutMs: int = 100000;

    // 0 - nothing, 1 - one-line messages, 2 - timings, 3 - full stack traces
    static debugCallLogLevel: int = 2;
    static debugErrorLogLevel: int = 3;

    printErrorIfNeeded(e: Error) {
        if (BBBrowser.debugErrorLogLevel > 0) {
            if (BBBrowser.debugErrorLogLevel > 2) {
                console.trace();
            }
            console.log(`Got exception ${e}`);
        }
    }

    printTimingsIfNeeded(startTimeMs: number) {
        if (BBBrowser.debugCallLogLevel > 1) {
            const endTimeMs = new Date().getTime();
            const durationS = (endTimeMs - startTimeMs) / 1000.0;
            console.log(`                                               ... Took ${durationS} s`);
        }
    }

    printEntryMessageIfNeeded(functionName: string, params: string) {
        if (BBBrowser.debugCallLogLevel > 0) {
            if (BBBrowser.debugCallLogLevel > 2) {
                console.trace();
            }
            console.log(`${functionName}(${params})`);
        }
    }

    async wait(condition: Function, message: string) {
        this.printEntryMessageIfNeeded('bbrowser.wait', message);

        let start = new Date().getTime()
        try {
            await browser.wait(condition, BBBrowser.defaultTimeoutMs, message);

            this.printTimingsIfNeeded(start);
            if (BBBrowser.debugCallLogLevel > 2) {
                console.trace();
            }
        }
        catch (e) {
            this.printTimingsIfNeeded(start);
            this.printErrorIfNeeded(e);

            throw e;
        }
    }

    async get(url: string) {
        this.printEntryMessageIfNeeded('bbrowser.get', url);

        let start = new Date().getTime()

        try {
            await browser.get(url);

            this.printTimingsIfNeeded(start);
            if (BBBrowser.debugCallLogLevel > 2) {
                console.trace();
            }
        }
        catch (e) {
            this.printTimingsIfNeeded(start);
            this.printErrorIfNeeded();

            throw e;
        }
    }
};

const bbrowser = new BBBrowser();
export { bbrowser };
