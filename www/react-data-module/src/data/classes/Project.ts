/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {Builder, builderDescriptor} from "./Builder";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export class Project extends BaseClass {
  @observable projectid!: number;
  @observable description!: string|null;
  @observable slug!: string[];
  @observable name!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.projectid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.projectid = object.projectid;
    this.name = object.name;
    this.slug = object.slug;
    this.description = object.description;
  }

  toObject() {
    return {
      projectid: this.projectid,
      name: this.name,
      slug: this.slug,
      description: this.description,
    };
  }

  getBuilders(query: RequestQuery = {}) {
    return this.get<Builder>("builders", query, builderDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get("projects", query, projectDescriptor);
  }
}

export class ProjectDescriptor implements IDataDescriptor<Project> {
  restArrayField = "projects";
  fieldId: string = "projectid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Project(accessor, endpoint, object);
  }
}

export const projectDescriptor = new ProjectDescriptor();
