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

import renderer, {act} from 'react-test-renderer';
import {MemoryRouter} from "react-router-dom";
import RawData from './RawData';
import {observable} from "mobx";

function assertRenderSnapshot(data: {[key: string]: any}) {
  const component = renderer.create(
    <MemoryRouter>
      <RawData data={data}/>
    </MemoryRouter>
  );
  expect(component.toJSON()).toMatchSnapshot();
}

function assertRenderSnapshotExpanded(data: {[key: string]: any}) {
  const component = renderer.create(
    <MemoryRouter>
      <RawData data={data}/>
    </MemoryRouter>
  );
  act(() =>
    component.root.findByType("i").props.onClick()
  );
  expect(component.toJSON()).toMatchSnapshot();
}

describe('RawData component', function() {
  it('simple object', () => {
    const obj = {
      str: "string",
      int: 123,
      float: 123.4,
      boolean: true,
      array: [321, "string", true],
    }

    assertRenderSnapshot(obj);
  });

  it('observable object', () => {
    const obj = observable({
      str: "string",
      int: 123,
      float: 123.4,
      boolean: true,
      array: observable([321, "string", true]),
    });

    assertRenderSnapshot(obj);
  });

  it('object with array of objects', () => {
    const obj = {
      array: [
        {str: "string"},
        {int: 123},
        {float: 123.4},
        {boolean: true},
      ],
    };

    assertRenderSnapshot(obj);
  });

  it('object with array of objects expanded', () => {
    const obj = {
      array: [
        {str: "string"},
        {int: 123},
        {float: 123.4},
        {boolean: true},
      ],
    };

    assertRenderSnapshotExpanded(obj);
  });

  it('observable object with array of objects', () => {
    const obj = observable({
      array: [
        observable({str: "string"}),
        observable({int: 123}),
        observable({float: 123.4}),
        observable({boolean: true}),
      ],
    });

    assertRenderSnapshot(obj);
  });
});
