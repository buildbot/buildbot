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

import {Step} from "../data/classes/Step";
import {Build} from "../data/classes/Build";
import {Buildrequest} from "../data/classes/Buildrequest";

export const SUCCESS = 0;
export const WARNINGS = 1;
export const FAILURE = 2;
export const SKIPPED = 3;
export const EXCEPTION = 4;
export const RETRY = 5;
export const CANCELLED = 6;
// Not returned by the API
export const PENDING = 1000;
export const UNKNOWN = 1001;

const intToResult: {[key: number]: string} = {
  [SUCCESS]: "SUCCESS",
  [WARNINGS]: "WARNINGS",
  [FAILURE]: "FAILURE",
  [SKIPPED]: "SKIPPED",
  [EXCEPTION]: "EXCEPTION",
  [RETRY]: "RETRY",
  [CANCELLED]: "CANCELLED",
  [PENDING]: "PENDING",
  [UNKNOWN]: "UNKNOWN",
};

export const intToColor: {[key: number]: string} = {
  [SUCCESS]: '#8d4',
  [WARNINGS]: '#fa3',
  [FAILURE]: '#e88',
  [SKIPPED]: '#AADDEE',
  [EXCEPTION]: '#c6c',
  [RETRY]: '#ecc',
  [CANCELLED]: '#ecc',
  [PENDING]: '#E7D100',
  [UNKNOWN]: '#EEE',
}

export function getBuildOrStepResults(buildOrStep: Build | Step | null, unknownResults: number) {
  if (buildOrStep === null) {
    return unknownResults;
  }
  if ((buildOrStep.results !== null) && buildOrStep.results in intToResult) {
    return buildOrStep.results;
  }
  if ((buildOrStep.complete === false) && ((buildOrStep.started_at ?? 0) > 0)) {
    return PENDING;
  }
  return unknownResults;
}

export function results2class(buildOrStep: Build | Step, pulse: string | null) {
  const results = getBuildOrStepResults(buildOrStep, UNKNOWN);
  let ret = `results_${intToResult[results]}`
  if (results === PENDING && pulse !== null) {
    ret += ` ${pulse}`;
  }
  return ret;
}

export function results2text(objWithResults: Build | Step | Buildrequest) {
  let ret = "...";
  if (objWithResults !== null) {
    if ((objWithResults.results !== null) && objWithResults.results in intToResult) {
      ret = intToResult[objWithResults.results];
    }
  }
  return ret;
}
