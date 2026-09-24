PYTHON ?= python3
TESTS ?=
BACKUP ?=
export TESTS BACKUP

.PHONY: all setup check up down clean fclean re logs ps smoke test reset-db backup restore
all setup check up down clean fclean re logs ps smoke test reset-db backup restore:
	@$(PYTHON) scripts/make.py $@
