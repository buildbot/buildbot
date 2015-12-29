class Change extends Factory
    constructor: (Base, dataService, dataUtilsService) ->
        return class ChangeInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
                author = @author
                if not @author?
                    author = "unknown"

                email = dataUtilsService.emailInString(author)
                # Remove email from author string
                if email
                    if  author.split(' ').length > 1
                        @author_name = author.replace(///\s<#{email}>///, '')
                        @author_email = email
                    else
                        @author_name = email.split("@")[0]
                        @author_email = email
                else
                    @author_name = author
