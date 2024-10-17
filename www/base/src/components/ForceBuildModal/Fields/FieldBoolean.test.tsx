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
import {render} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FieldBoolean } from "./FieldBoolean";
import { ForceSchedulerFieldBoolean } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

async function assertRenderToSnapshot(defaultValue: boolean, stateValue?: boolean, updateValue: boolean = false) {
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
    tooltip: 'dummy',
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (stateValue !== undefined) {
    state.setValue(field.fullName, stateValue);
  }

  const component = render(
    <FieldBoolean field={field} fieldsState={state} />
  );
  expect(component.asFragment()).toMatchSnapshot();

  if (updateValue) {
    const previousState = state.getValue(field.fullName);
    const expectedState = !previousState;
    const checkbox = component.getByTestId(`force-field-${field.fullName}`) as HTMLInputElement;
    if (checkbox.checked !== expectedState) {
      await userEvent.click(checkbox);
    }
    expect(state.getValue(field.fullName)).toBe(expectedState);
  }
}

describe('ForceFieldBoolean component', function () {
  it('render default value False', async () => {
    await assertRenderToSnapshot(false);
  });

  it('render default value True', async () => {
    await assertRenderToSnapshot(true);
  });

  it('render non-default value False', async () => {
    await assertRenderToSnapshot(true, false);
  });

  it('render non-default value True', async () => {
    await assertRenderToSnapshot(false, true);
  });

  it('change state on click', async () => {
    await assertRenderToSnapshot(true, true, true);
  });
});
