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

export class Buildset extends BaseClass {
  bsid!: number;
  complete!: boolean;
  complete_at!: number|null;
  external_idstring!: string|null;
  parent_buildid!: number|null;
  parent_relationship!: string|null;
  reason!: string;
  results!: number|null;
  sourcestamps!: string[]; // TODO
  submitted_at!: number|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.bsid));
    this.update(object);
  }

  update(object: any) {
    this.bsid = object.bsid;
    this.complete = object.complete;
    this.complete_at = object.complete_at;
    this.external_idstring = object.external_idstring;
    this.parent_buildid = object.parent_buildid;
    this.parent_relationship = object.parent_relationship;
    this.reason = object.reason;
    this.results = object.results;
    this.sourcestamps = object.sourcestamps; // FIXME
    this.submitted_at = object.submitted_at;
  }

  toObject() {
    return {
      bsid: this.bsid,
      complete: this.complete,
      complete_at: this.complete_at,
      external_idstring: this.external_idstring,
      parent_buildid: this.parent_buildid,
      parent_relationship: this.parent_relationship,
      reason: this.reason,
      results: this.results,
      sourcestamps: this.sourcestamps,
      submitted_at: this.submitted_at,
    };
  }

  getProperties(query: RequestQuery = {}) {
    return this.getPropertiesImpl("properties", query);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Buildset>("buildsets", query, buildsetDescriptor);
  }
}

export class BuildsetDescriptor implements IDataDescriptor<Buildset> {
  restArrayField = "buildsets";
  fieldId: string = "bsid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Buildset(accessor, endpoint, object);
  }
}

export const buildsetDescriptor = new BuildsetDescriptor();
