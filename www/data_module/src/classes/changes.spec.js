describe('change class', function() {
    beforeEach(angular.mock.module('bbData'));

    it('should calculate authors emails', inject(function(Change) {
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
        expect(changes[2].author_name).toBe("foo");
    })
    );
});
