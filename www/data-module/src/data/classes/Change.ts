/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {Sourcestamp} from "./Sourcestamp";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";
import {Build, buildDescriptor} from "./Build";

export class Change extends BaseClass {
  @observable changeid!: number;
  @observable author!: string;
  @observable branch!: string|null;
  @observable category!: string|null;
  @observable codebase!: string;
  @observable comments!: string;
  @observable files!: string[];
  @observable parent_changeids!: number[];
  @observable project!: string;
  @observable properties!: {[key: string]: any}; // for subscription to properties use getProperties
  @observable repository!: string;
  @observable revision!: string|null;
  @observable revlink!: string|null;
  @observable sourcestamp!: Sourcestamp;
  @observable when_timestamp!: number;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.changeid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.changeid = object.changeid;
    this.author = object.author;
    this.branch = object.branch;
    this.category = object.category;
    this.codebase = object.codebase;
    this.comments = object.comments;
    this.files = object.files;
    this.parent_changeids = object.parent_changeids;
    this.project = object.project;
    this.properties = object.properties ?? {};
    this.repository = object.repository;
    this.revision = object.revision;
    this.revlink = object.revlink;
    this.sourcestamp = object.sourcestamp;
    this.when_timestamp = object.when_timestamp;
  }

  toObject() {
    return {
      changeid: this.changeid,
      author: this.author,
      branch: this.branch,
      category: this.category,
      codebase: this.codebase,
      comments: this.comments,
      files: this.files,
      parent_changeids: this.parent_changeids,
      project: this.project,
      properties: this.properties,
      repository: this.repository,
      revision: this.revision,
      revlink: this.revlink,
      sourcestamp: this.sourcestamp,
      when_timestamp: this.when_timestamp,
    };
  }

  getBuilds(query: RequestQuery = {}) {
    return this.get<Build>("builds", query, buildDescriptor);
  }

  getProperties(query: RequestQuery = {}) {
    return this.getPropertiesImpl("properties", query);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Change>("changes", query, changeDescriptor);
  }
}

export class ChangeDescriptor implements IDataDescriptor<Change> {
  restArrayField = "changes";
  fieldId: string = "changeid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Change(accessor, endpoint, object);
  }
}

export const changeDescriptor = new ChangeDescriptor();
