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
import { FieldString } from "./FieldString";
import { ForceSchedulerFieldString } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

async function assertRenderToSnapshot(defaultValue: string, stateValue?: string, updateValue?: string) {
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
    tooltip: 'dummy',
    size: 0,
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (stateValue !== undefined) {
    state.setValue(field.fullName, stateValue.toString());
  }

  const component = render(
    <FieldString field={field} fieldsState={state} />
  );
  expect(component.asFragment()).toMatchSnapshot();

  if (updateValue !== undefined) {
    const expectedState = updateValue;
    const input = component.getByTestId(`force-field-${field.fullName}`);
    await userEvent.clear(input);
    await userEvent.type(input, expectedState);
    expect(state.getValue(field.fullName)).toBe(expectedState);
  }
}

describe('ForceFieldString component', function () {
  it('render default value', async () => {
    await assertRenderToSnapshot("");
    await assertRenderToSnapshot("default");
  });

  it('render non-default value', async () => {
    await assertRenderToSnapshot("default", "stateValue");
  });

  it('change state on click', async () => {
    await assertRenderToSnapshot("default", "stateValue", "updateValue");
  });
});
