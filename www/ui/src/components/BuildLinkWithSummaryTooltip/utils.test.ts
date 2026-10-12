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

import {Build} from 'buildbot-data-js';
import {describe, expect, it} from 'vitest';
import {defaultBuildLinkTemplate, formatBuildLinkTextWithTemplate} from './utils';

const makeBuild = (properties: {[key: string]: any}): Build => {
  return {
    number: 123,
    properties: properties,
  } as Build;
};

describe('formatBuildLinkTextWithTemplate', () => {
  it('formats the default build link with the branch name when it is set', () => {
    expect(
      formatBuildLinkTextWithTemplate(
        makeBuild({
          branch: ['main', 'Build'],
        }),
        defaultBuildLinkTemplate,
      ),
    ).toEqual('main (123)');
  });

  it('omits the default branch wrapper when the branch name is empty', () => {
    expect(
      formatBuildLinkTextWithTemplate(
        makeBuild({
          branch: ['', 'Build'],
        }),
        defaultBuildLinkTemplate,
      ),
    ).toEqual('123');
  });

  it('leaves custom templates unchanged', () => {
    expect(
      formatBuildLinkTextWithTemplate(
        makeBuild({
          branch: ['', 'Build'],
        }),
        'build %(build_number) %(prop:branch)',
      ),
    ).toEqual('build 123 ');
  });
});
