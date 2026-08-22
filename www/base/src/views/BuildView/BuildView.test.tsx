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
import {DataPropertiesCollection} from 'buildbot-data-js';
import {getResponsibleUsers} from './BuildView';

const makePropertiesQuery = (properties: {[key: string]: any}) => {
  const query = new DataPropertiesCollection();
  for (const [key, value] of Object.entries(properties)) {
    query.properties.set(key, [value, 'test']);
  }
  return query;
};

describe('getResponsibleUsers', () => {
  it('empty properties and no changes', () => {
    expect(getResponsibleUsers(makePropertiesQuery({}), new Set())).toEqual({});
  });

  it('owner in name-email format', () => {
    expect(
      getResponsibleUsers(makePropertiesQuery({owner: 'John Doe <john@doe.org>'}), new Set()),
    ).toEqual({'John Doe': 'john@doe.org'});
  });

  it('owner as plain email', () => {
    expect(getResponsibleUsers(makePropertiesQuery({owner: 'john@doe.org'}), new Set())).toEqual({
      john: 'john@doe.org',
    });
  });

  it('owner as plain name', () => {
    expect(getResponsibleUsers(makePropertiesQuery({owner: 'john'}), new Set())).toEqual({
      john: null,
    });
  });

  it('owners list with mixed formats', () => {
    expect(
      getResponsibleUsers(
        makePropertiesQuery({owners: ['John Doe <john@doe.org>', 'jane@doe.org', 'sam']}),
        new Set(),
      ),
    ).toEqual({'John Doe': 'john@doe.org', jane: 'jane@doe.org', sam: null});
  });

  it('owner and owners are deduplicated by name', () => {
    expect(
      getResponsibleUsers(
        makePropertiesQuery({owner: 'john@doe.org', owners: ['john@doe.org', 'sam']}),
        new Set(),
      ),
    ).toEqual({john: 'john@doe.org', sam: null});
  });

  it('change authors are merged with owners', () => {
    expect(
      getResponsibleUsers(
        makePropertiesQuery({owner: 'john@doe.org'}),
        new Set(['Jane Doe <jane@doe.org>', 'john']),
      ),
    ).toEqual({john: 'john@doe.org', 'Jane Doe': 'jane@doe.org'});
  });

  it('author with email takes precedence over name-only entry', () => {
    expect(
      getResponsibleUsers(
        makePropertiesQuery({owners: ['john']}),
        new Set(['john <john@doe.org>']),
      ),
    ).toEqual({john: 'john@doe.org'});
  });

  it('non-string owner values are ignored', () => {
    expect(
      getResponsibleUsers(makePropertiesQuery({owner: 123, owners: [null, 42, 'sam']}), new Set()),
    ).toEqual({sam: null});
  });
});
