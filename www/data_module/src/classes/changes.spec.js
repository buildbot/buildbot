/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('change class', function() {
    beforeEach(angular.module('bbData'));

    return it('should calculate authors emails', inject(function(Change) {
        const changes = [
            new Change({author: "foo <bar@foo.com>"}, "changes")
        ,
            new Change({author: "foo@foo.com"}, "changes")
        ,
            new Change({author: "foo"}, "changes")
        ];
        expect(changes[0].author_email).toBe("bar@foo.com");
        expect(changes[1].author_email).toBe("foo@foo.com");
        expect(changes[2].author_email).toBeUndefined();
        expect(changes[0].author_name).toBe("foo");
        expect(changes[1].author_name).toBe("foo");
        return expect(changes[2].author_name).toBe("foo");
    })
    );
});
