# gli4py
A aysnc python 3 API wrapper for GL-inet routers with version 4 firmware. [WIP]

[GL-inet](https://www.gl-inet.com/) routers are built on [OpenWRT](https://openwrt.org/). They are highly customizeable but have an attractive user interface.

As part of their modiification of the UI they used to provide a [documented locally accessible API](https://web.archive.org/web/20240121142533/https://dev.gl-inet.com/router-4.x-api/).

I thought it would be handy to develop a python 3 wrapper for the API for easy intergation into other services such as [HomeAssistant](https://www.home-assistant.io/)

## Installation
`pip3 install gli-py`

## Dev setup
1. Clone the repo
2. Ensure you have python 3.11 or greater installed `python3 -V` or `python -V`
3. Uses poetry for venv control `pip3 install poetry`
4. `poetry config virtualenvs.in-project true` create the venvs in the project folder
5. `poetry install`
6. `poetry env activate`
7. To run unit tests (no router required): `poetry run pytest -m "not live"`
8. To run hardware tests, ensure there is a file called `router_pwd` in the root directory with the router password in.
   Then run `PYTHONDEVMODE="" PYTHONASYNCIODEBUG="" poetry run pytest` to see responses, assumes the router is at `192.168.0.1`
9. Set up pre-commit hooks: `poetry run pre-commit install` (or run manually with `poetry run pre-commit run --all-files`)
10. Set token with `poetry config pypi-token.pypi TOKEN`
11. Publish with `poetry publish --build`


## Dev setup alongside HA & the Custom component
1. Clone the repo into the vscode `/workspaces/` dir
2. The inside the `ha-env` terminal run `(ha-venv) vscode ➜ /workspaces/core (branch-name) $ pip install -e /workspaces/gli4py `
3. Ensure the custom component has `"python.analysis.extraPaths": ["/workspaces/gli4py/"]` in `.vscode/settings.json`
4. deactivate the `ha-env` with `deactivate`
5. Do steps 3 onwards above

Todo list:
- [ ] Decide on useful endpoints to expose - see https://github.com/HarvsG/ha-glinet-integration#todo
- [ ] Expose said endpoints
- [ ] Write remaining
- [x] Package correctly
- [x] Test that dev enviroment is re-producable
- [x] Publish on pip
- [ ] Static typing
