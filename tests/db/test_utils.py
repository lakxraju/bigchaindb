import builtins

import pytest
import rethinkdb as r

import bigchaindb
from bigchaindb import util
from bigchaindb.db import utils
from .conftest import setup_database as _setup_database


# Since we are testing database initialization and database drop,
# we need to use the `setup_database` fixture on a function level
@pytest.fixture(scope='function', autouse=True)
def setup_database(request, node_config):
    _setup_database(request, node_config)


def test_init_creates_db_tables_and_indexes():
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures so we need to remove it
    r.db_drop(dbname).run(conn)

    utils.init()

    assert r.db_list().contains(dbname).run(conn) is True

    assert r.db(dbname).table_list().contains('backlog', 'bigchain').run(conn) is True

    assert r.db(dbname).table('bigchain').index_list().contains(
        'block_timestamp',
        'block_number').run(conn) is True

    assert r.db(dbname).table('backlog').index_list().contains(
        'transaction_timestamp',
        'assignee__transaction_timestamp').run(conn) is True


def test_init_fails_if_db_exists():
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures
    assert r.db_list().contains(dbname).run(conn) is True

    with pytest.raises(bigchaindb.exceptions.DatabaseAlreadyExists):
        utils.init()


def test_drop_interactively_drops_the_database_when_user_says_yes(monkeypatch):
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures
    assert r.db_list().contains(dbname).run(conn) is True

    monkeypatch.setattr(builtins, 'input', lambda x: 'y')
    utils.drop()

    assert r.db_list().contains(dbname).run(conn) is False


def test_drop_programmatically_drops_the_database_when_assume_yes_is_true(monkeypatch):
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures
    assert r.db_list().contains(dbname).run(conn) is True

    utils.drop(assume_yes=True)

    assert r.db_list().contains(dbname).run(conn) is False


def test_drop_interactively_does_not_drop_the_database_when_user_says_no(monkeypatch):
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures
    print(r.db_list().contains(dbname).run(conn))
    assert r.db_list().contains(dbname).run(conn) is True

    monkeypatch.setattr(builtins, 'input', lambda x: 'n')
    utils.drop()

    assert r.db_list().contains(dbname).run(conn) is True

def test_drop_non_existent_db_raises_an_error():
    conn = utils.get_conn()
    dbname = bigchaindb.config['database']['name']

    # The db is set up by fixtures
    assert r.db_list().contains(dbname).run(conn) is True
    utils.drop(assume_yes=True)

    with pytest.raises(bigchaindb.exceptions.DatabaseDoesNotExist):
        utils.drop(assume_yes=True)

