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

import {describe, expect, it} from 'vitest';
import {getResponsibleUsers} from './BuildView';

describe('getResponsibleUsers', () => {
  it('includes owner and owners build properties', () => {
    const properties = {
      owner: ['Forced User <forced@example.com>', 'ForceScheduler'],
      owners: [
        ['fallback@example.com', 'Changed User <changed@example.com>', 'no-email-owner'],
        'Build',
      ],
    };

    const responsibleUsers = getResponsibleUsers(
      properties,
      new Set(['Changed User <changed@example.com>', 'Commit Author <commit@example.com>']),
    );

    expect(responsibleUsers).toEqual({
      'Forced User': 'forced@example.com',
      fallback: 'fallback@example.com',
      'Changed User': 'changed@example.com',
      'no-email-owner': null,
      'Commit Author': 'commit@example.com',
    });
  });
});
