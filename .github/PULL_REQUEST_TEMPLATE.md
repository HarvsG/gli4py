## Description

<!-- Describe the changes introduced by this pull request and the rationale behind them. -->

## Related Issues & Pull Requests

<!-- Optional: Link to a relevant issue or pull request in https://github.com/HarvsG/ha-glinet4-integration -->
- Relevant integration PR: 

## Checklist

- [ ] Code complies with repository style guidelines (`ruff format`, `ruff check`, `pylint`)
- [ ] All tests pass locally (`pytest --disruptive-tests`)
- [ ] Every new or modified public (non-private) method has an entry and example in `examples.md`
- [ ] Every new or modified API call is supported by `gli4py.mock.MockRouter`
- [ ] A sanitized JSON fixture is added to `tests/fixtures/` for any new response payloads (no sensitive credentials, private IPs, or real MAC addresses)
