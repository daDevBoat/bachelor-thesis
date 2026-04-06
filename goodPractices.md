# Decided work conventions in the group:

## Versions:
- We use **java 25**
- We use **springframework 4.0.2** as our server framework
- We use **Junit 5.10.1** as our test framework
- We use **spring.dependency-management 1.1.7**
- We use **Spotless 8.2.1** for stylechecking


## Way of working:
0) Create an issue if a task is identified
    - Every issue should have a useful description

1) Make a new branch for every issue 
    - The branch should be name `issue/x`, where x is the issue number

2) When working on the issue
    - Every function and method should have a docstring. See how to write good docstrings [here](https://dev.to/arshisaxena26/mastering-javadoc-how-to-document-your-java-code-5hhf)
    - Every function, fix, or new feature should be tested

3) Commit all work regarding issue `x` to branch `issue/x`
    - **Every** bug fix or feature commit contains a test
    - **Every** commit reflects the commit message
    - **Every** commit message should link to the issue by having `#x` in the end.
    - **Every** commit message should start with a prefix like **"feat", "fix", "doc", "refactor"**, find more [here](https://gist.github.com/qoomon/5dfcdf8eec66a051ecd85625518cfd13).

4) When the work is done, **rebase** the issue branch on main 
    - **squash** all commits into one
    - Have a commit message summarizing all the commits, include the *close trigger* for the issue `closes #x`

5) Push the branch to GitHub

6) If all tests pass on GitHub create a pull request
    - Make sure to use `squash and merge` when merging into main
    - Make sure to start with **"feat", "fix", "doc", "refactor, etc"** 
    - Reference the issue **both** in the merge message **AND** at the end of the title
        - *Example:* feat: add validation check for event type (#39) #37

