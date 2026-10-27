# Backup: protein-information-system branch `fix/surface-task-failures`

Temporary copy of a PIS branch, kept here until it is pushed to a fork of
CBBIO/protein-information-system. It is not part of FANTASIA.

Base commit: `41999c3` (CBBIO/protein-information-system `main`, version 3.1.2).

Restore it in a clone of protein-information-system:

    git checkout -b fix/surface-task-failures 41999c3
    git am /path/to/patches/*.patch

or, from the bundle:

    git fetch /path/to/pis-fix-surface-task-failures.bundle fix/surface-task-failures:fix/surface-task-failures

`PR_DESCRIPTION.md` contains the pull request description.

`FANTASIA_PR_DESCRIPTION.md` is the description for the companion FANTASIA pull
request (branch `fix/open-issues-4.1.2` of this fork), kept here until that
pull request is opened.
