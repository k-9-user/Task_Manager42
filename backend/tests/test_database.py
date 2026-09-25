from alembic import command


def test_the_migration_matches_the_models(alembic_config):
    command.check(alembic_config)
