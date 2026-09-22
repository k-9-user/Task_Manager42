PYTHON ?= python3
TESTS ?=
export TESTS

.PHONY: setup check up down clean fclean re logs ps smoke test reset-db backup
setup check up down clean fclean re logs ps smoke test reset-db backup:
	@$(PYTHON) scripts/make.py $@
