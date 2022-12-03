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

import "./AboutView.scss";
import {observer} from "mobx-react";
import {Card} from "react-bootstrap";
import {DataClientContext} from "../../data/ReactUtils";
import {useContext, useState} from "react";
import {ConfigContext} from "../../contexts/Config";
import {globalMenuSettings} from "../../plugins/GlobalMenuSettings";
import {Link} from "react-router-dom";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {
  EndpointDescription,
  EndpointFieldSpec,
  useApplicationSpec
} from "../../data/ApplicationSpec";
import RawData from "../../components/RawData/RawData";

type EndpointListItemProps = {
  spec: EndpointDescription;
}

const EndpointListItem = ({spec}: EndpointListItemProps) => {
  const [showDetail, setShowDetail] = useState<boolean>(false);

  const renderDetailedDescription = () => {
    if (spec.type_spec.fields === undefined) {
      return <></>;
    }
    const fields : EndpointFieldSpec[] = spec.type_spec.fields;
    fields.sort((a, b) => a.name.localeCompare(b.name));

    return (
      <dl className="dl-horizontal">
        {
          fields.map((field) => {
            return (
              <span>
                <dt>{field.name}</dt>
                <dd>
                  {field.type}
                  {field.type === 'list' ? <span>{JSON.stringify(field.type_spec)}</span> : <></>}
                </dd>
              </span>
            )
          })
        }
      </dl>
    )
  };

  const fieldCount = spec.type_spec.fields !== undefined ? spec.type_spec.fields.length : 0;

  return (
    <li key={spec.path} className="list-group-item">
      <b onClick={(e) => { setShowDetail(!showDetail); }}>
        /{spec.path}:
      </b>{fieldCount} fields
      { showDetail ? renderDetailedDescription() : <></> }
    </li>
  )
}

const AboutView = observer(() => {
  const config = useContext(ConfigContext);

  const dataClient = useContext(DataClientContext);
  const applicationSpecs = useApplicationSpec(dataClient);

  return (
    <div className="container bb-about-view">
      <Card bg="light">
        <Card.Body>
          <h2>
            <img src="img/icon.svg" alt="" width="64px" className="nut-spin"/>&nbsp;About this&nbsp;
            <Link to="http://buildbot.net">buildbot</Link>&nbsp;running for&nbsp;
            <Link to={config.titleURL}>{config.title}</Link>
          </h2>
          <div className="col-sm-12">
            <ul>
              {
                config.versions.map(version => (
                  <li key={version[0]}>{version[0]} version: {version[1]}</li>
                ))
              }
            </ul>
          </div>
        </Card.Body>
      </Card>
      <Card bg="light">
        <Card.Body>
          <h2>Configuration</h2>buildbot-www is configured using
          <RawData data={config}></RawData>
        </Card.Body>
      </Card>
      <Card bg="light">
        <Card.Body>
          <h2>API description</h2>
          <ul className="list-group">
            { applicationSpecs
                .sort((a, b) => a.path.localeCompare(b.path))
                .map(spec => (<EndpointListItem spec={spec}/>)) }
          </ul>
        </Card.Body>
      </Card>
    </div>
  )
});

globalMenuSettings.addGroup({
  name: 'about',
  caption: 'About',
  icon: 'info-circle',
  order: 99,
  route: '/about',
  parentName: null,
});

globalRoutes.addRoute({
  route: "/about",
  group: null,
  element: () => <AboutView/>,
});

export default AboutView;
