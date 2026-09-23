PYTHON ?= python3
TESTS ?=
BACKUP ?=
export TESTS BACKUP

.PHONY: setup check up down clean fclean re logs ps smoke test reset-db backup restore
setup check up down clean fclean re logs ps smoke test reset-db backup restore:
	@$(PYTHON) scripts/make.py $@
