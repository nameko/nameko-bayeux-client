test: flake8 pylint pytest

flake8:
	flake8 nameko_bayeux_client tests

pylint:
	pylint nameko_bayeux_client -E

pytest:
	coverage run --concurrency=eventlet --source nameko_bayeux_client --branch -m pytest tests
	coverage report --show-missing --fail-under=100
