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

import {describe, expect, it} from "vitest";
import renderer from 'react-test-renderer';
import { FieldBoolean } from "./FieldBoolean";
import { ForceSchedulerFieldBoolean } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

function assertRenderToSnapshot(defaultValue: boolean, stateValue?: boolean, updateValue: boolean = false) {
  const field: ForceSchedulerFieldBoolean = {
    name: 'dummy',
    fullName: 'fullDummy',
    label: 'dummyLabel',
    tablabel: 'dummyTabLabel',
    type: 'bool',
    default: defaultValue,
    multiple: false,
    regex: null,
    hide: false,
    maxsize: null,
    autopopulate: null,
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (stateValue !== undefined) {
    state.setValue(field.fullName, stateValue);
  }

  const component = renderer.create(
    <FieldBoolean field={field} fieldsState={state} />
  );
  expect(component.toJSON()).toMatchSnapshot();

  if (updateValue) {
    const previousState = state.getValue(field.fullName);
    const expectedState = !previousState;
    renderer.act(() => {
      const elements = component.root.findAllByProps({'data-bb-test-id': `force-field-${field.fullName}`}, {deep: true});
      expect(elements.length).toBe(1);
      const checkbox = elements[0];
      checkbox.props.onChange({target: {checked: expectedState}});
    });
    expect(state.getValue(field.fullName)).toBe(expectedState);
  }
}

describe('ForceFieldBoolean component', function () {
  it('render default value False', () => {
    assertRenderToSnapshot(false);
  });

  it('render default value True', () => {
    assertRenderToSnapshot(true);
  });

  it('render non-default value False', () => {
    assertRenderToSnapshot(true, false);
  });

  it('render non-default value True', () => {
    assertRenderToSnapshot(false, true);
  });

  it('change state on click', () => {
    assertRenderToSnapshot(true, true, true);
  });
});
