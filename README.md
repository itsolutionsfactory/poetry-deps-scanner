# Poetry dependencies scanner & gitlab commenter

This project consists of two scripts.

One analyses the `poetry.lock` and `pyproject.toml` files
it receives and produces an output listing the outdated
packages.

The other takes an input and posts it as a comment on a Gitlab
merge request.

Here's how we use them:

```yaml
# .gitlab-ci.yml

scan-deps:
  stage: test
  image: deps-scanner
  allow_failure: true
  script:
    - scan-deps poetry.lock pyproject.toml | comment-gitlab
  only:
    - merge_requests
```

The `deps-scanner` image is built from the Dockerfile in this repository.

Here's an example of what the output looks like in a merge request for
this repository:

![Comment screenshot](img/comment-screenshot.png)

## Installation

```bash
python -m pip install poetry-deps-scanner
```

## Dependencies analysis

The following snippet is an example output the first script may produce:

```
direct devpi command-log: current=0.0.28 -> latest=0.0.29
direct pypi  django: current=3.1.9 -> latest=3.2.1
direct pypi  semver: current=3.0.0.dev2 -> latest=2.13.0
trans. pypi  idna: current=2.10 -> latest=3.1
```

The first column indicates whether the package is a direct or transitive
dependency:
* `direct` means the package is a direct dependency.
* `trans.` means the package is a transitive dependency: the dependency
  of a direct dependency or of a transitive dependency.

This is computed by using the `pyproject.toml` if given. If this file is
not provided on the command line, the column will be omitted.

A dependency is considered direct if it is present in the `pyproject.toml`.

The second column indicates whether the package comes from PyPi or
a devpi instance.

## Gitlab comment

The `comment_gitlab.py` script requires some environment variables
to properly work:

* `BOT_USERNAME`: The username for the bot user
* `BOT_TOKEN`: A Gitlab access token for the bot user
  (see https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
* `CI_SERVER_URL`: The URL of the Gitlab instance where to post
* `CI_PROJECT_ID`: The ID of the project containing the MR to post on
* `CI_MERGE_REQUEST_IID`: The IID of the merge request to comment on

The last three variables are automatically populated by Gitlab CI when
running a job as part of a detached pipeline (for a merge request). Notice
the `only: [merge_requests]` in the `.gitlab-ci.yml` above.

Of course, you can also provide them manually to integrate with any other build
system.

If a comment from the bot user already exists, it will be replaced,
in order to reduce the noise. In other words, there will be at most one
comment from the bot on a given merge request. It will contain the results of
the latest check.

## Build the docker image outside ITSF

The Dockerfile inside the repository references images from our internal
Docker registry proxy. You can easily build it on your own by removing
the `nexus.itsf.io:5005/` prefix.

```bash
# on Ubuntu
sed -i 's/nexus.itsf.io:5005\///g' Dockerfile
# on macOS
sed -e 's/nexus.itsf.io:5005\///g' -i "" Dockerfile
# then
docker build -t deps-scanner .
```
