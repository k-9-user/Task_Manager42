PYTHON ?= python3
TESTS ?=
export TESTS

.PHONY: setup check up down clean fclean re logs ps smoke test reset-db
setup check up down clean fclean re logs ps smoke test reset-db:
	@$(PYTHON) scripts/make.py $@
