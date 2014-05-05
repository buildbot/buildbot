from buildbot.www.authz import Authz
from buildbot.www.authz.roles import RolesFromGroups, RolesFromEmails, RolesFromOwner
from buildbot.www.authz.endpointmatchers import AnyEndpointMatcher
from buildbot.www.authz.endpointmatchers import ForceBuildEndpointMatcher
from buildbot.www.authz.endpointmatchers import BranchEndpointMatcher
from buildbot.www.authz.endpointmatchers import ViewBuildsEndpointMatcher
from buildbot.www.authz.endpointmatchers import StopBuildEndpointMatcher

authz = Authz(
    stringsMatcher=Authz.fnmatchMatcher,  # simple matcher with '*' glob character
    # stringsMatcher = Authz.reMatcher,  # if you prefer regular expressions
    allowRules=[
        # admins can do anything,
        # defaultDeny=False: if user does not have the admin role, we continue parsing rules
        AnyEndpointMatcher(role="admins", defaultDeny=False),

        # rules for viewing builds, builders, step logs
        # depending on the sourcestamp or buildername
        ViewBuildsEndpointMatcher(branch="secretbranch", role="agents"),
        ViewBuildsEndpointMatcher(project="secretproject", role="agents"),
        ViewBuildsEndpointMatcher(branch="*", role="*"),
        ViewBuildsEndpointMatcher(project="*", role="*"),

        StopBuildEndpointMatcher(role="owner"),

        # nine-* groups can do stuff on the nine branch
        BranchEndpointMatcher(branch="nine", role="nine-*"),
        # eight-* groups can do stuff on the eight branch
        BranchEndpointMatcher(branch="eight", role="eight-*"),

        # *-try groups can start "try" builds
        ForceBuildEndpointMatcher(builder="try", role="*-try"),
        # *-mergers groups can start "merge" builds
        ForceBuildEndpointMatcher(builder="merge", role="*-mergers"),
        # *-releasers groups can start "release" builds
        ForceBuildEndpointMatcher(builder="release", role="*-releasers"),
    ],
    roleMatchers=[
        RolesFromGroups(groupPrefix="buildbot-"),
        RolesFromEmails(admins=["homer@springfieldplant.com"],
                        agents=["007@mi6.uk"]),
        RolesFromOwner(role="owner")
    ]
)
c['www'] = dict(authz=authz)
