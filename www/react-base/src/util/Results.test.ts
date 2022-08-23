/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

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
