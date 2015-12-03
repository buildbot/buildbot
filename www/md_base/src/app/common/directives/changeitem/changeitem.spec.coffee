beforeEach module 'app'

describe 'changeitem', ->
    $compile = $rootScope = $httpBackend = null
    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')

    beforeEach inject injected

    today = new Date()

    # mock object for test
    test_change =
        author: 'testauthor <test@email.com>'
        comments: 'test comments'
        when_timestamp: (new Date(today.getFullYear(), today.getMonth(), today.getDate())).getTime()/1000
        repository: 'testrepo'
        branch: 'testbranch'
        revision: 'abcdefghijk'
        files: [
            'testfile1',
            'testfile2',
            'testfile3',
        ]


    it 'should display information correctly', ->
        $rootScope.change = test_change
        elem = $compile('<change-item change="change"></change-item>')($rootScope)
        $rootScope.$digest()

        # test on change-item when it is collapsed (detail not showing)
        expect(elem.children().length).toBe(1)
        inner = elem.children().eq(0)
        expect(inner.children().length).toBe(3)

        author = inner.children().eq(0)
        comment = inner.children().eq(1)
        revision = inner.children().eq(2)

        expect(author.attr('title')).toBe(test_change.author)
        expect(author.attr('href')).toBe('mailto:test@email.com')
        expect(comment.text()).toBe(test_change.comments)
        expect(revision.text()).toBe('abcdef')

        avatar = author.children().eq(0)
        # test img url to the users avatar
        expect(avatar.attr('src')).toBe('avatar?email=test@email.com')


    it 'should show detail correctly', ->
        $rootScope.change = test_change
        elem = $compile('<change-item change="change"></change-item>')($rootScope)
        $rootScope.$digest()

        expect(elem.children().length).toBe(1)
        inner = elem.children().eq(0)
        comment = inner.children().eq(1)
        # Expand the directive and show detail
        comment.triggerHandler('click')
        expect(elem.children().length).toBe(2)

        # Detail should be showing
        detail = elem.children().eq(1)
        expect(detail.children().length).toBe(4)

        # Retrieve components
        meta = detail.children().eq(0)
        comment = detail.children().eq(1).children().eq(1)
        files = detail.children().eq(2).children()
        data = detail.children().eq(3).children().eq(0)

        # Displaying date time 
        date = meta.children().eq(0)
        expect(date.attr('title')).toBe('Today at 12:00 AM')

        # Displaying author
        authortitle = meta.children().eq(1)
        expect(authortitle.text().trim()).toBe(test_change.author)

        # Displaying comment
        expect(comment.text()).toBe(test_change.comments)

        # Displaying changed files
        expect(files.length - 1).toBe(test_change.files.length)
        for i in [0...3]
            expect(files.eq(i + 1).text()).toBe(test_change.files[i])

        # Displaying extra data
        expect(data.children().length).toBe(3)
        for i in [0...3]
            row = data.children().eq(i)
            key = row.children().eq(0).text()
            value = row.children().eq(1).text()
            switch key
                when 'Repository'
                    expect(value).toBe(test_change.repository)
                when 'Branch'
                    expect(value).toBe(test_change.branch)
                when 'Revision'
                    expect(value).toBe(test_change.revision)
                else
                    expect(key).toBe('')
