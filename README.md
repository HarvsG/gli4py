# gli4py
A aysnc python 3 API wrapper for GL-inet routers with version 4 firmware. [WIP]

[GL-inet](https://www.gl-inet.com/) routers are built on [OpenWRT](https://openwrt.org/). They are highly customizeable but have an attractive user interface.

As part of their modiification of the UI they provide a [locally accessible API](https://dev.gl-inet.com/api).

I thought it would be handy to develop a python 3 wrapper for the API for easy intergation into other services such as [HomeAssistant](https://www.home-assistant.io/)

## Installation
`pip3 install gli-py`

## Dev setup
1. Clone the repo
2. Ensure you have python 3 installed `python3 -V` or `python -V`
3. Uses poetry for venv control `pip3 install poetry`
4. `poetry config virtualenvs.in-project true` create the venvs in the project folder
5. `poetry install`
6. `poetry shell`
7. To run tests, ensure there is a file called `router_pwd` in the root directory with the router password in.
8. Then run `pytest -s` to see responses, assumes the router is at `192.168.0.1`
9. Set token with `poetry config pypi-token.pypi TOKEN`
10. publish with `poetry publish --build`

Todo list:
- [ ] Decide on useful endpoints to expose - see https://github.com/HarvsG/ha-glinet-integration#todo
- [ ] Expose said endpoints
- [ ] Write remaining
- [x] Package correctly
- [x] Test that dev enviroment is re-producable
- [x] Publish on pip
- [ ] Static typing
