# Changelog

## v0.1.1-beta - 2026-09-10

## What's Changed
* Fix release/docker workflows never firing after tag-on-version-bump by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/8
* Fix workflow_dispatch on release.yml/docker.yml to take an explicit tag by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/9
* Remove bogus 'main' entry from CHANGELOG.md by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/10
* Add regression test for the B->A->B slide rollback direction by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/11
* Add a real example-output section to the README by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/12
* Polish README: badges, contents nav, docs table by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/13
* Make offline/local-only operation visible in the README header by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/14
* Bump version to 0.1.1-beta by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/15


**Full Changelog**: https://github.com/kajisho5/event-recording-auditor/compare/v0.1.0-beta...v0.1.1-beta


## v0.1.0-beta - 2026-09-10

## What's Changed
* Implement Event Recording Auditor: deterministic anomaly detection + post-production comparison by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/1
* Add release automation (tag push → GitHub Release with auto-generated notes) by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/2
* Add lint CI, Dependabot, Docker image, CHANGELOG automation, auto-tag-on-version-bump by @kajisho5 in https://github.com/kajisho5/event-recording-auditor/pull/3


**Full Changelog**: https://github.com/kajisho5/event-recording-auditor/commits/v0.1.0-beta


New entries are added automatically (newest first) by
`.github/workflows/release.yml` whenever a version tag is published --
see README.md, "Releasing a version".
