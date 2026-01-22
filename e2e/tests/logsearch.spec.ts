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

import {expect, test, Page} from "@playwright/test";
import {BuilderPage} from "./pages/builder";
import {ForcePage} from "./pages/force";
import {LogPage} from "./pages/log";

type Case = { builder: string; force: string; label: string; term: string };

const CASES: Case[] = [
  { builder: "logtests",     force: "force_logtests",     label: "plain", term: "LINE_010000" },
  { builder: "ansilogtests", force: "force_ansilogtests", label: "ansi",  term: "LINE_010000" },
];

async function runSearchFlow(page: Page, c: Case) {
  await BuilderPage.goto(page, c.builder);
  const buildnumber = await BuilderPage.getLastFinishedBuildNumber(page);
  await BuilderPage.gotoForce(page, c.builder, c.force);
  await ForcePage.clickStartButtonAndWaitRedirectToBuild(page);
  await BuilderPage.goto(page, c.builder);
  await BuilderPage.waitBuildFinished(page, buildnumber + 1);
  await BuilderPage.gotoBuild(page, c.builder, `${buildnumber + 1}`);
  await LogPage.openFullStdioFromSummary(page, 'shell');
  await LogPage.waitForStdioUrl(page);
  await LogPage.search(page, c.term);
  await LogPage.assertSearchHighlight(page, c.term);
  await LogPage.assertNoAnsiInOutput(page)
}

test.describe('search full stdio log', () => {
  for (const c of CASES) {
    test(`should search in ${c.label} log`, async ({page}) => {
      await runSearchFlow(page, c);
    });
  }
});
