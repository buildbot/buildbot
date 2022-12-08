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

import {useMemo} from "react";
import {StepUrl} from "../data/classes/Step";

export type BuildInfoByUrls = {
  builderid: string;
  buildnumber: string;
}

export type BuildRequestInfoByUrls = {
  buildrequestid: string;
}

export type StepInfoByUrls = {
  buildrequests: BuildRequestInfoByUrls[];
  builds: BuildInfoByUrls[];
  otherUrls: StepUrl[];
}

const execRegexesGetFirstResult = (regexes: RegExp[], text: string) => {
  for (const regex of regexes) {
    const res = regex.exec(text)
    if (res) {
      return res
    }
  }
  return null
}

export type StepUrlAnalyzer = {
  buildrequest: RegExp[];
  build: RegExp[];
};

export function useStepUrlAnalyzer(baseUrls: string[]): StepUrlAnalyzer {
  const buildrequestRegexes = useMemo(
    () => baseUrls.map(url => new RegExp(`${url}#/buildrequests/([0-9]+)$`)),
    [baseUrls]);
  const buildRegexes = useMemo(
    () => baseUrls.map(url => new RegExp(`${url}#/builders/([0-9]+)/builds/([0-9]+)$`)),
    [baseUrls]);

  return {
    buildrequest: buildrequestRegexes,
    build: buildRegexes,
  };
}

export function analyzeStepUrls(analyzer: StepUrlAnalyzer, urls: StepUrl[]): StepInfoByUrls {
  const info: StepInfoByUrls = {
    buildrequests: [],
    builds: [],
    otherUrls: [],
  };

  for (let url of urls) {
    let brRes = execRegexesGetFirstResult(analyzer.buildrequest, url.url)
    if (brRes !== null) {
      info.buildrequests.push({
        buildrequestid: brRes[1],
      })
      continue;
    }
    let buildRes = execRegexesGetFirstResult(analyzer.build, url.url)
    if (buildRes !== null) {
      info.builds.push({
        builderid: buildRes[1],
        buildnumber: buildRes[2],
      })
      continue;
    }

    info.otherUrls.push(url);
  }

  return info;
}
