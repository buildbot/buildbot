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
import { FieldChoiceString } from "./FieldChoiceString";
import { ForceSchedulerFieldChoiceString } from 'buildbot-data-js';
import { ForceBuildModalFieldsState } from '../ForceBuildModalFieldsState';

type FieldChoiceStringTestOptions = {
  defaultValue: string | string[];
  stateValue?: string | string[];
  updateValueTo?: string[];
  multiple?: boolean;
  strict?: boolean;
}

async function assertRenderToSnapshot(options: FieldChoiceStringTestOptions) {
  const field: ForceSchedulerFieldChoiceString = {
    name: 'dummy',
    fullName: 'fullDummy',
    label: 'dummyLabel',
    tablabel: 'dummyTabLabel',
    type: 'list',
    default: options.defaultValue,
    multiple: options.multiple ?? false,
    regex: null,
    hide: false,
    maxsize: null,
    autopopulate: null,
    tooltip: 'dummy',
    choices: ['A', 'B', 'C'],
    strict: options.strict ?? true,
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (options.stateValue !== undefined) {
    state.setValue(field.fullName, options.stateValue);
  }

  const component = render(
    <FieldChoiceString field={field} fieldsState={state} />
  );
  expect(component.asFragment()).toMatchSnapshot();

  if (options.updateValueTo !== undefined) {
    if (!field.multiple) {
      expect(options.updateValueTo.length).toBe(1);
    }

    const expectedState = options.updateValueTo;

    const element = component.getByTestId(`force-field-${field.fullName}`);
    if (!field.multiple) {
      expect(expectedState.length).toBe(1);
      await userEvent.selectOptions(element, expectedState[0]);
    }
    else {
      const currentValue: string[] = state.getValue(field.fullName);
      // click elements not in expected to unselect them
      for (const value of currentValue.filter(e => !(expectedState.includes(e)))) {
        await userEvent.selectOptions(element, value);
      }
      // then click elements not currently selected
      for (const value of expectedState.filter(e => !(currentValue.includes(e)))) {
        await userEvent.selectOptions(element, value);
      }
    }

    if (field.multiple) {
      const stateValue: string[] = state.getValue(field.fullName);
      stateValue.sort();
      expectedState.sort();
      expect(stateValue).toStrictEqual(expectedState);
    }
    else {
      expect(state.getValue(field.fullName)).toBe(expectedState[0]);
    }
  }
}

describe('ForceFieldChoiceString component', function () {
  it('render default value', async () => {
    await assertRenderToSnapshot({ defaultValue: 'A' });
    await assertRenderToSnapshot({ defaultValue: 'B' });
  });

  it('render multiple default value', async () => {
    await assertRenderToSnapshot({ defaultValue: ['A'], multiple: true });
    await assertRenderToSnapshot({ defaultValue: ['A', 'B'], multiple: true });
  });

  it('render non-default value', async () => {
    await assertRenderToSnapshot({ defaultValue: 'A', stateValue: 'B' });
  });

  it('render multiple non-default value', async () => {
    await assertRenderToSnapshot({ defaultValue: ['A'], stateValue: ['B', 'C'], multiple: true });
  });

  it('change state on click', async () => {
    await assertRenderToSnapshot({ defaultValue: 'A', stateValue: 'B', updateValueTo: ['C'] });
  });

  it('change multiple state on click', async () => {
    await assertRenderToSnapshot({ defaultValue: ['A'], stateValue: ['B', 'C'], updateValueTo: ['A', 'C'], multiple: true });
  });
});
