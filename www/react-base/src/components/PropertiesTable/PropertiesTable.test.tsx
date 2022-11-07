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

import renderer from 'react-test-renderer';
import {MemoryRouter} from "react-router-dom";
import PropertiesTable from './PropertiesTable';

function assertRenderSnapshot(properties: Map<string, any>) {
  const component = renderer.create(
    <MemoryRouter>
      <PropertiesTable properties={properties}/>
    </MemoryRouter>
  );
  expect(component.toJSON()).toMatchSnapshot();
}

describe('PropertiesTable component', function() {
  it('rendering', () => {
    const obj = {
      str: ["string", "string source"],
      int: [123, "int source"],
      float: [123.4, "float source"],
      boolean: [true, "boolean source"],
      array: [[321, "astr", false], "array source"],
      object: [{s: "str", i: 789, b: false}, "object source"],
    }

    assertRenderSnapshot(new Map(Object.entries(obj)));
  });
});
