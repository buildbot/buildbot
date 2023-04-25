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

export class Sourcestamp extends BaseClass {
  @observable ssid!: number;
  @observable branch!: string|null;
  @observable codebase!: string;
  @observable created_at!: number;
  @observable patch!: string|null; // TODO
  @observable project!: string;
  @observable repository!: string;
  @observable revision!: string|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.ssid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.ssid = object.ssid;
    this.branch = object.branch;
    this.codebase = object.codebase;
    this.created_at = object.created_at;
    this.patch = object.patch;
    this.project = object.project;
    this.repository = object.repository;
    this.revision = object.revision;
  }

  toObject() {
    return {
      ssid: this.ssid,
      branch: this.branch,
      codebase: this.codebase,
      created_at: this.created_at,
      patch: this.patch,
      project: this.project,
      repository: this.repository,
      revision: this.revision,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Sourcestamp>("sourcestamps", query, sourcestampDescriptor);
  }
}

export class SourcestampDescriptor implements IDataDescriptor<Sourcestamp> {
  restArrayField = "sourcestamps";
  fieldId: string = "ssid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Sourcestamp(accessor, endpoint, object);
  }
}

export const sourcestampDescriptor = new SourcestampDescriptor();
