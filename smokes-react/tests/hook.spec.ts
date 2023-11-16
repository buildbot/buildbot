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

import {expect, test} from "@playwright/test";
import {post} from 'request';
import {BuilderPage} from './pages/builder';
import {HomePage} from './pages/home';
import {testPageUrl} from './pages/base';

test.describe('change hook', function() {
  test.afterEach(async ({page}) => {
    await HomePage.waitAllBuildsFinished(page);
  });

  test('should create a build', async ({page}) => {
    await BuilderPage.goto(page, "runtests1");
    const lastbuild = await BuilderPage.getLastFinishedBuildNumber(page);
    await post(`${testPageUrl}/change_hook/base`).form({
      comments: 'sd',
      project: 'pyflakes',
      repository: 'https://github.com/buildbot/hello-world.git',
      author: 'foo <foo@bar.com>',
      committer: 'foo <foo@bar.com>',
      revision: 'HEAD',
      branch: 'master'
    });
    await BuilderPage.waitBuildFinished(page, lastbuild + 1);
    expect(await BuilderPage.getBuildResult(page, lastbuild + 1)).toEqual("SUCCESS");
  });
});
