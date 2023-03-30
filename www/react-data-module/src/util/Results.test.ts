/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {results2class, results2text, RETRY, SUCCESS} from "./Results";

describe('results2class', () => {
  it('simple', () => {
    const results2classStep = (r: number) => results2class(<any>{results: r}, null);

    expect(results2classStep(SUCCESS)).toBe("results_SUCCESS");
    expect(results2classStep(RETRY)).toBe("results_RETRY");
    expect(results2classStep(1234)).toBe("results_UNKNOWN");
    expect(results2class(<any>{results:undefined}, null)).toBe("results_UNKNOWN");

    expect(results2class(<any>{
      results: null,
      complete: false,
      started_at: undefined
    }, null)).toBe("results_UNKNOWN");

    expect(results2class(<any>{
        results: null,
        complete: false,
        started_at: 10
      }, "pulse"
    )).toBe("results_PENDING pulse");
  });
});

describe('results2Text', () => {
  it('simple', () => {
    const results2textStep = (r: number) => results2text(<any>{results: r});

    expect(results2textStep(SUCCESS)).toBe("SUCCESS");
    expect(results2textStep(RETRY)).toBe("RETRY");
    expect(results2textStep(1234)).toBe("...");
    expect(results2text(<any>{results: undefined})).toBe("...");

    expect(results2text(<any>{
      results: null,
      complete: false,
      started_at: null
    })).toBe("...");

    expect(results2text(<any>{
      results: null,
      complete: false,
      started_at: 10
    })).toBe("...");
  });
});
