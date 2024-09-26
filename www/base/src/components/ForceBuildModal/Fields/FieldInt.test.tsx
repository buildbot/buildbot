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
import { FieldInt } from "./FieldInt";
import { ForceSchedulerFieldInt } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

async function assertRenderToSnapshot(defaultValue: number, stateValue?: number, updateValue?: number) {
  const field: ForceSchedulerFieldInt = {
    name: 'dummy',
    fullName: 'fullDummy',
    label: 'dummyLabel',
    tablabel: 'dummyTabLabel',
    type: 'int',
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
    state.setValue(field.fullName, stateValue);
  }

  const component = render(
    <FieldInt field={field} fieldsState={state} />
  );
  expect(component.asFragment()).toMatchSnapshot();

  if (updateValue !== undefined) {
    const expectedState = updateValue;
    const input = component.getByTestId(`force-field-${field.fullName}`) as HTMLInputElement;
    await userEvent.clear(input);
    await userEvent.type(input, expectedState.toString());
    expect(state.getValue(field.fullName)).toBe(expectedState);
  }
}

describe('ForceFieldInt component', function () {
  it('render default value', async () => {
    await assertRenderToSnapshot(0);
    await assertRenderToSnapshot(-0);
    await assertRenderToSnapshot(150);
    await assertRenderToSnapshot(-150);
  });

  it('render non-default value', async () => {
    await assertRenderToSnapshot(0, -0);
    await assertRenderToSnapshot(0, 150);
    await assertRenderToSnapshot(0, -150);
  });

  it('change state on click', async () => {
    await assertRenderToSnapshot(0, -150, 350);
  });
});
