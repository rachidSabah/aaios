## Summary of Changes
Describe the modifications introduced by this PR and their structural purpose.

## Quality Assurance Checklist
Verify that your changes satisfy all of the following requirements:
* [ ] Code formatting and style rules pass cleanly (run `aaios validate --lint`).
* [ ] Strict type safety checks pass without issues (run `aaios validate --type-check`).
* [ ] The entire unit test suite passes 100% (run `aaios validate --test`).
* [ ] No hardcoded secrets are introduced.
* [ ] Subprocesses do not use raw shells (`shell=True`).
