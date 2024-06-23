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

function assertRenderToSnapshot(options: FieldChoiceStringTestOptions) {
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
    choices: ['A', 'B', 'C'],
    strict: options.strict ?? true,
  }
  const state = new ForceBuildModalFieldsState();
  state.createNewField(field.fullName, field.default);
  if (options.stateValue !== undefined) {
    state.setValue(field.fullName, options.stateValue);
  }

  const component = renderer.create(
    <FieldChoiceString field={field} fieldsState={state} />
  );
  expect(component.toJSON()).toMatchSnapshot();

  if (options.updateValueTo !== undefined) {
    if (!field.multiple) {
      expect(options.updateValueTo.length).toBe(1);
    }

    const expectedState = options.updateValueTo;

    const toClick: string[] = [];
    if (!field.multiple) {
      expect(expectedState.length).toBe(1);
      toClick.push(expectedState[0]);
    }
    else {
      const currentValue: string[] = state.getValue(field.fullName);
      // click elements not in expected to unselect them
      toClick.push(...currentValue.filter(e => !(expectedState.includes(e))));
      // then click elements not currently selected
      toClick.push(...expectedState.filter(e => !(currentValue.includes(e))));
    }

    renderer.act(() => {
      const elements = component.root.findAll(
        (node) => {
          return node.props['data-bb-test-id'] === `force-field-${field.fullName}` && node.type !== 'select';
        },
        { deep: true }
      );
      expect(elements.length).toBe(1);
      const select = elements[0];
      for (const element of toClick) {
        select.props.onChange({ target: { value: element } });
      }
    });

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
  it('render default value', () => {
    assertRenderToSnapshot({ defaultValue: 'A' });
    assertRenderToSnapshot({ defaultValue: 'B' });
  });

  it('render multiple default value', () => {
    assertRenderToSnapshot({ defaultValue: ['A'], multiple: true });
    assertRenderToSnapshot({ defaultValue: ['A', 'B'], multiple: true });
  });

  it('render non-default value', () => {
    assertRenderToSnapshot({ defaultValue: 'A', stateValue: 'B' });
  });

  it('render multiple non-default value', () => {
    assertRenderToSnapshot({ defaultValue: ['A'], stateValue: ['B', 'C'], multiple: true });
  });

  it('change state on click', () => {
    assertRenderToSnapshot({ defaultValue: 'A', stateValue: 'B', updateValueTo: ['C'] });
  });

  it('change multiple state on click', () => {
    assertRenderToSnapshot({ defaultValue: ['A'], stateValue: ['B', 'C'], updateValueTo: ['A', 'C'], multiple: true });
  });
});
