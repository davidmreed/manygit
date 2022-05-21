deps:
	pip install pip-tools
	pip-compile requirements/dev.in > requirements/dev.txt
	pip-compile requirements/prod.in > requirements/prod.txt

dev-install: deps
	pip-sync requirements/*.txt

test:
	pytest --cov=manygit tests --cov-report xml:cov.xml --block-network
