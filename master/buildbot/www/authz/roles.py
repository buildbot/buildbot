
class RolesFromBase(object):
    def __init__(self):
        pass

    def getRolesFromUser(self, userDetails, owner):
        return []


class RolesFromGroups(RolesFromBase):
    def __init__(self, groupPrefix=""):
        RolesFromBase.__init__(self)
        self.groupPrefix = groupPrefix

    def getRolesFromUser(self, userDetails, owner):
        roles = []
        if 'groups' in userDetails:
            for group in userDetails['groups']:
                if group.startsWith(self.groupPrefix):
                    roles.append(group[len(self.groupPrefix):])
        return roles


class RolesFromEmails(RolesFromBase):
    def __init__(self, **kwargs):
        RolesFromBase.__init__(self)
        self.roles = {}
        for role, emails in kwargs.iteritems():
            for email in emails:
                self.roles.setdefault(email, []).append(role)

    def getRolesFromUser(self, userDetails, owner):
        if 'email' in userDetails:
            return self.roles.get(userDetails['email'], [])
        return []


class RolesFromOwner(RolesFromBase):
    def __init__(self, role):
        RolesFromBase.__init__(self)
        self.role = role

    def getRolesFromUser(self, userDetails, owner):
        if 'email' in userDetails:
            if userDetails['email'] == owner and owner is not None:
                return self.role
        return []
