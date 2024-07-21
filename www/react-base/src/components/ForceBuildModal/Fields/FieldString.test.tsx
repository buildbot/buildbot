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
import { FieldString } from "./FieldString";
import { ForceSchedulerFieldString } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

function assertRenderToSnapshot(defaultValue: string, stateValue?: string, updateValue?: string) {
  const field: ForceSchedulerFieldString = {
    name: 'dummy',
    fullName: 'fullDummy',
    label: 'dummyLabel',
    tablabel: 'dummyTabLabel',
    type: 'text',
    default: defaultValue,
    multiple: false,
    regex: null,
    hide: false,
    maxsize: null,
    autopopulate: null,
    size: 0,
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (stateValue !== undefined) {
    state.setValue(field.fullName, stateValue.toString());
  }

  const component = renderer.create(
    <FieldString field={field} fieldsState={state} />
  );
  expect(component.toJSON()).toMatchSnapshot();

  if (updateValue !== undefined) {
    const expectedState = updateValue;
    renderer.act(() => {
      const elements = component.root.findAllByProps({'data-bb-test-id': `force-field-${field.fullName}`}, {deep: true});
      expect(elements.length).toBe(1);
      const input = elements[0];
      input.props.onChange({target: {value: expectedState}});
    });
    expect(state.getValue(field.fullName)).toBe(expectedState);
  }
}

describe('ForceFieldString component', function () {
  it('render default value', () => {
    assertRenderToSnapshot("");
    assertRenderToSnapshot("default");
  });

  it('render non-default value', () => {
    assertRenderToSnapshot("default", "stateValue");
  });

  it('change state on click', () => {
    assertRenderToSnapshot("default", "stateValue", "updateValue");
  });
});
