## Description

<!-- Describe the changes introduced by this pull request and the rationale behind them. -->

## Related Issues & Pull Requests

<!-- Optional: Link to a relevant issue or pull request in https://github.com/HarvsG/ha-glinet4-integration -->
- Relevant integration PR:

## Live Hardware Testing (Optional)

<!-- If tested against a physical GL.iNet router, specify the device details below: -->
- Router Model:
- Firmware Version:

## Checklist

- [ ] Code complies with repository style guidelines (`ruff format`, `ruff check`, `pylint`)
- [ ] All tests pass locally (`pytest --disruptive-tests`)
- [ ] Tested against live GL.iNet hardware (if applicable/available):
  ```bash
  poetry run pytest tests/test_api.py --live --url 192.168.8.1 --password <router-password>
  # Add --disruptive-tests if testing actions that reboot or mutate router state:
  # poetry run pytest tests/test_api.py --live --url 192.168.8.1 --password <router-password> --disruptive-tests
  ```
- [ ] Every new or modified public (non-private) method has an entry and example in `examples.md`
- [ ] Every new or modified API call is supported by `gli4py.mock.MockRouter`
- [ ] A sanitized JSON fixture is added to `tests/fixtures/` for any new response payloads (no sensitive credentials, private IPs, or real MAC addresses)
