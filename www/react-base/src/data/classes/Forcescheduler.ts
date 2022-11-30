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

import BaseClass from "./BaseClass";
import IDataDescriptor from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

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
}

export type ForceSchedulerFieldFixed = ForceSchedulerFieldBase & {
  // type: 'fixed'
}

export type ForceSchedulerFieldString = ForceSchedulerFieldBase & {
  // type: 'text'
  size: number;
}

export type ForceSchedulerFieldText = ForceSchedulerFieldString & {
  // type: 'textarea'
  rows: number;
  cols: number;
}

export type ForceSchedulerFieldInt = ForceSchedulerFieldString & {
  // type: 'int'
}

export type ForceSchedulerFieldBoolean = ForceSchedulerFieldBase & {
  // type: 'bool'
}

export type ForceSchedulerFieldUserName = ForceSchedulerFieldString & {
  // type: 'username'
}

export type ForceSchedulerFieldChoiceString = ForceSchedulerFieldBase & {
  // type: 'choices'
  choices: string[];
  strict: boolean;
}

// Not properly supported yet
export type ForceSchedulerFieldInheritBuild = ForceSchedulerFieldChoiceString & {
  // type: 'inherit'
}

export type ForceSchedulerFieldNested = ForceSchedulerFieldBase & {
  // type: 'nested'
  layout: string;
  columns: number | null;
  fields: ForceSchedulerFieldBase[];
}

export class Forcescheduler extends BaseClass {
  name!: string;
  all_fields!: ForceSchedulerFieldBase[];
  builder_names!: string[];
  button_name!: string;
  label!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, object.name);
    this.update(object);
  }

  update(object: any) {
    this.name = object.name;
    this.all_fields = object.all_fields;
    this.builder_names = object.builder_names;
    this.button_name = object.button_name;
    this.label = object.label;
  }

  toObject() {
    return {
      name: this.name,
      all_fields: this.all_fields,
      builder_names: this.builder_names,
      button_name: this.button_name,
      label: this.label,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Forcescheduler>("forceschedulers", query, forceschedulerDescriptor);
  }
}

export class ForceschedulerDescriptor implements IDataDescriptor<Forcescheduler> {
  restArrayField = "forceschedulers";
  fieldId: string = "name";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Forcescheduler(accessor, endpoint, object);
  }
}

export const forceschedulerDescriptor = new ForceschedulerDescriptor();
