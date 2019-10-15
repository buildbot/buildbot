/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Change {
    constructor(Base, dataService, dataUtilsService) {
        let ChangeInstance;
        return (ChangeInstance = class ChangeInstance extends Base {
            constructor(object, endpoint) {
                super(object, endpoint);
                let { author } = this;
                if ((this.author == null)) {
                    author = "unknown";
                }

                const email = dataUtilsService.emailInString(author);
                // Remove email from author string
                if (email) {
                    if  (author.split(' ').length > 1) {
                        this.author_name = author.replace(new RegExp(`\\s<${email}>`), '');
                        this.author_email = email;
                    } else {
                        this.author_name = email.split("@")[0];
                        this.author_email = email;
                    }
                } else {
                    this.author_name = author;
                }
            }
        });
    }
}


angular.module('bbData')
.factory('Change', ['Base', 'dataService', 'dataUtilsService', Change]);
