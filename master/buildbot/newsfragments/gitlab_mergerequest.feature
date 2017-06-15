GitLab merge request hook now create a change with repository to be the source repository and branch the source branch.
Additional properties are created to point to destination branch and destination repository.
This makes :bb:reporter:`GitLabStatusPush` push the correct status to GitLab, so that pipeline report is visible in the merge request page.
