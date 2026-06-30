# Contribution Guidelines

## Content

## Style Guide

All checks are enforced by `husky` and the pre-commit configurations.

### Commit Style

`commitlint` is enabled for this project. This is checked whenever a commit is made.
The style for the commit is configured to be **Conventional Commits**.

More on the conventional commit format can be found at <https://www.conventionalcommits.org/en/v1.0.0>

### Code Linter

Run `eslint` and `prettier` together

```bash
pnpm lint --fix
```

Run `eslint` without auto fixing error

```bash
pnpm lint
```

Only format the code

```bash
pnpm format
```

## Docker Build Instructions

To build the docker locally, first remove the existing `node_modules` folders.

For Linux users, you can use this shortcut command (ignore any errors).

```bash
find -type d -name node_modules -exec rm -rf {} \;
```

Build the docker image

```bash
docker build . -t rmf2-ui/dashboard:latest
```

Run the docker image

```bash
docker run -p 3000:80 --rm rmf2-ui/dashboard:latest
```
