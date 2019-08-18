/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
describe('notificationService', function() {
    beforeEach(angular.mock.module("guanlecoja.ui"));

    it('should add and delete notifications', inject(function(glNotificationService, $timeout) {

        glNotificationService.notify({msg:"done", title:"finish"});
        expect(glNotificationService.notifications).toEqual([ { id : 1, msg : 'done', title : 'finish' } ]);
        glNotificationService.dismiss(1);
        expect(glNotificationService.notifications).toEqual([]);

        glNotificationService.notify({msg:"done", title:"finish", group:"group"});
        glNotificationService.notify({msg:"msg2", title:"finish", group:"group"});
        expect(glNotificationService.notifications).toEqual([ { id : 2, msg : 'done\nmsg2', title : 'finish', group:"group" } ]);
        glNotificationService.dismiss(2);
        expect(glNotificationService.notifications).toEqual([]);

        glNotificationService.network({msg:"404"});
        glNotificationService.network({msg:"404", title:"403"});
        glNotificationService.network({msg:"404", group:"Network"});
        glNotificationService.dismiss(4);
        glNotificationService.error({msg:"oups"});
        glNotificationService.error({msg:"oups", title:"error"});
        glNotificationService.dismiss(8);
        expect(glNotificationService.notifications[0].id).toEqual(7);
        glNotificationService.dismiss(7);
        glNotificationService.dismiss(99);

        expect(glNotificationService.notifications).toEqual([]);

        glNotificationService.notify({msg:"done1", title:"finish"});
        glNotificationService.notify({msg:"done2", title:"finish", group:"group"});
        glNotificationService.notify({msg:"done3", title:"finish", group:"group"});
        glNotificationService.dismiss(9);
        glNotificationService.dismiss(10);
        expect(glNotificationService.notifications).toEqual([]);
    })
    );
});
