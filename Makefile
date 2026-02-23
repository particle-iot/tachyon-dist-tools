install: .venv/deps_installed.stamp

.venv/deps_installed.stamp: requirements.txt pyproject.toml
	if [ ! -d .venv ]; then python3 -m venv .venv; fi
	. .venv/bin/activate; \
	pip install --upgrade pip; \
	pip install '.[dev]'; \
	pip install -e .;
	touch .venv/deps_installed.stamp
