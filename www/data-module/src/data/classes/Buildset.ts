/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

// This class is effectively same as Sourcestamp except that it is returned as part of a Buildset
// and not as a separate entity identified by id, like in the rest of the API.
export type BuildsetSourcestamps = {
  ssid: number;
  branch: string|null;
  codebase: string;
  created_at: number;
  patch: string|null;
  project: string;
  repository: string;
  revision: string|null;
}

export class Buildset extends BaseClass {
  @observable bsid!: number;
  @observable complete!: boolean;
  @observable complete_at!: number|null;
  @observable external_idstring!: string|null;
  @observable parent_buildid!: number|null;
  @observable parent_relationship!: string|null;
  @observable reason!: string;
  @observable rebuilt_buildid!: number|null;
  @observable results!: number|null;
  @observable sourcestamps!: BuildsetSourcestamps[];
  @observable submitted_at!: number|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.bsid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.bsid = object.bsid;
    this.complete = object.complete;
    this.complete_at = object.complete_at;
    this.external_idstring = object.external_idstring;
    this.parent_buildid = object.parent_buildid;
    this.parent_relationship = object.parent_relationship;
    this.reason = object.reason;
    this.rebuilt_buildid = object.rebuilt_buildid;
    this.results = object.results;
    this.sourcestamps = object.sourcestamps;
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
      rebuilt_buildid: this.rebuilt_buildid,
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
