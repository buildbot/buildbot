/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from 'mobx';
import {BaseClass} from './BaseClass';
import {IDataDescriptor} from './DataDescriptor';
import {IDataAccessor} from '../DataAccessor';
import {RequestQuery} from '../DataQuery';

// Union types are not used because this makes it impossible to inherit properties and share
// behaviors across related types.
export type ForceSchedulerFieldBase = {
  name: string;
  fullName: string;
  label: string;
  tablabel: string;
  type: string;
  default: any;
  multiple: boolean;
  regex: string | null;
  hide: boolean;
  maxsize: number | null;
  autopopulate: boolean | null;
  tooltip: string;
};

export type ForceSchedulerFieldFixed = ForceSchedulerFieldBase & {
  // type: 'fixed'
};

export type ForceSchedulerFieldString = ForceSchedulerFieldBase & {
  // type: 'text'
  size: number;
};

export type ForceSchedulerFieldText = ForceSchedulerFieldString & {
  // type: 'textarea'
  rows: number;
  cols: number;
};

export type ForceSchedulerFieldInt = ForceSchedulerFieldString & {
  // type: 'int'
};

export type ForceSchedulerFieldBoolean = ForceSchedulerFieldBase & {
  // type: 'bool'
};

export type ForceSchedulerFieldUserName = ForceSchedulerFieldString & {
  // type: 'username'
};

export type ForceSchedulerFieldChoiceString = ForceSchedulerFieldBase & {
  // type: 'list'
  choices: string[];
  strict: boolean;
};

// Not properly supported yet
export type ForceSchedulerFieldInheritBuild = ForceSchedulerFieldChoiceString & {
  // type: 'inherit'
};

export type ForceSchedulerFieldNested = ForceSchedulerFieldBase & {
  // type: 'nested'
  layout: string;
  columns: number | null;
  fields: ForceSchedulerFieldBase[];
};

export class Forcescheduler extends BaseClass {
  @observable name!: string;
  @observable all_fields!: ForceSchedulerFieldBase[];
  @observable builder_names!: string[];
  @observable button_name!: string;
  @observable label!: string;
  @observable tooltip!: string;

  constructor(accessor: IDataAccessor, object: any) {
    super(accessor, 'forceschedulers', object.name);
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.name = object.name;
    this.all_fields = object.all_fields;
    this.builder_names = object.builder_names;
    this.button_name = object.button_name;
    this.label = object.label;
    this.tooltip = object.tooltip;
  }

  toObject() {
    return {
      name: this.name,
      all_fields: this.all_fields,
      builder_names: this.builder_names,
      button_name: this.button_name,
      label: this.label,
      tooltip: this.tooltip,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Forcescheduler>('forceschedulers', query, forceschedulerDescriptor);
  }
}

export class ForceschedulerDescriptor implements IDataDescriptor<Forcescheduler> {
  restArrayField = 'forceschedulers';
  fieldId: string = 'name';

  parse(accessor: IDataAccessor, object: any) {
    return new Forcescheduler(accessor, object);
  }
}

export const forceschedulerDescriptor = new ForceschedulerDescriptor();
