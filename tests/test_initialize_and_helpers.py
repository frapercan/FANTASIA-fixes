import importlib
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

parasail = pytest.importorskip("parasail")

from fantasia.src.helpers import helpers  # noqa: E402
from fantasia.src.helpers.parser import DEFAULT_CONFIG_PATH  # noqa: E402

DB_CONF = {
    "DB_USERNAME": "usuario",
    "DB_PASSWORD": "clave",
    "DB_HOST": "localhost",
    "DB_PORT": 5432,
    "DB_NAME": "BioData",
}


# ---------------------------------------------------------------------------
# #60: empty sequences must not reach parasail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn", [helpers.run_needle_from_strings, helpers.run_smith_waterman_from_strings])
@pytest.mark.parametrize("seq1, seq2", [("", "MKV"), ("MKV", ""), ("", "")])
def test_alignment_with_empty_sequence_returns_missing_metrics(fn, seq1, seq2):
    result = fn(seq1, seq2)
    assert set(result) == {
        "identity_count", "alignment_length", "identity_percentage",
        "similarity_percentage", "gaps_percentage", "alignment_score",
    }
    assert all(value is None for value in result.values())


def test_compute_metrics_with_empty_reference_sequence():
    metrics = helpers.compute_metrics({"sequence_query": "MKVLA", "sequence_reference": None})
    assert metrics["identity"] is None
    assert metrics["identity_sw"] is None
    assert metrics["length_reference"] == 0


def test_alignment_of_identical_sequences_is_unchanged():
    result = helpers.run_needle_from_strings("MKVLA", "MKVLA")
    assert result["identity_percentage"] == 1.0


# ---------------------------------------------------------------------------
# #54: file:// URLs and local paths
# ---------------------------------------------------------------------------

def test_local_path_from_url(tmp_path):
    dump = tmp_path / "ref dump.backup"
    assert helpers.local_path_from_url(dump.as_uri()) == dump
    assert helpers.local_path_from_url(str(dump)) == dump
    assert helpers.local_path_from_url("https://zenodo.org/records/1/files/x.backup?download=1") is None


def test_download_embeddings_uses_local_file_in_place(tmp_path, monkeypatch):
    dump = tmp_path / "shared" / "ref.backup"
    dump.parent.mkdir()
    dump.write_bytes(b"PGDMP")
    monkeypatch.setattr(helpers.requests, "get", lambda *a, **k: pytest.fail("must not download"))

    result = helpers.download_embeddings(dump.as_uri(), tmp_path / "embeddings" / "ref.backup")

    assert result == dump
    assert not (tmp_path / "embeddings").exists()


def test_download_embeddings_missing_local_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        helpers.download_embeddings((tmp_path / "missing.backup").as_uri(), tmp_path / "out.backup")


# ---------------------------------------------------------------------------
# #57 / #61: pg_restore outcome
# ---------------------------------------------------------------------------

def _fake_restore(monkeypatch, returncode, stderr):
    monkeypatch.setattr(
        helpers.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=returncode, stdout="", stderr=stderr),
    )


def _dump(tmp_path):
    dump = tmp_path / "ref.backup"
    dump.write_bytes(b"PGDMP")
    return dump


def test_load_dump_reports_unsupported_dump_version(tmp_path, monkeypatch, caplog):
    _fake_restore(monkeypatch, 1, "pg_restore: error: unsupported version (1.16) in file header\n")
    with caplog.at_level(logging.ERROR):
        ok = helpers.load_dump_to_db(_dump(tmp_path), DB_CONF, drop_and_init=False)
    assert ok is False
    assert "PostgreSQL 18 client" in caplog.text


def test_load_dump_tolerates_transaction_timeout_on_older_server(tmp_path, monkeypatch):
    stderr = (
        "pg_restore: connecting to database for restore\n"
        "pg_restore: error: could not execute query: ERROR:  "
        "unrecognized configuration parameter \"transaction_timeout\"\n"
        "Command was: SET transaction_timeout = 0;\n"
        "pg_restore: creating TABLE \"public.sequence\"\n"
        "pg_restore: warning: errors ignored on restore: 1\n"
    )
    _fake_restore(monkeypatch, 1, stderr)
    assert helpers.load_dump_to_db(_dump(tmp_path), DB_CONF, drop_and_init=False) is True


def test_load_dump_fails_on_other_errors(tmp_path, monkeypatch):
    stderr = (
        "pg_restore: error: could not execute query: ERROR:  "
        "unrecognized configuration parameter \"transaction_timeout\"\n"
        "pg_restore: error: could not execute query: ERROR:  type \"vector\" does not exist\n"
        "pg_restore: warning: errors ignored on restore: 2\n"
    )
    _fake_restore(monkeypatch, 1, stderr)
    assert helpers.load_dump_to_db(_dump(tmp_path), DB_CONF, drop_and_init=False) is False


# ---------------------------------------------------------------------------
# #46: resources resolved independently of the working directory
# ---------------------------------------------------------------------------

def test_default_config_is_bundled_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(DEFAULT_CONFIG_PATH).is_file()
    assert Path(DEFAULT_CONFIG_PATH).name == "config.yaml"
    assert Path(DEFAULT_CONFIG_PATH).parent.name == "fantasia"


# ---------------------------------------------------------------------------
# #57 / #61: fantasia initialize must exit non-zero when the restore fails
# ---------------------------------------------------------------------------

def _load_main(monkeypatch, load_dump_result, download_calls):
    def module(name, **attrs):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    for name in (
        "protein_information_system",
        "protein_information_system.helpers",
        "protein_information_system.helpers.logger",
        "protein_information_system.helpers.config",
        "protein_information_system.helpers.services",
        "protein_information_system.sql",
        "protein_information_system.sql.model",
        "protein_information_system.sql.model.model",
    ):
        module(name)
    module("protein_information_system.helpers.logger.logger", setup_logger=lambda *a, **k: None)
    module("protein_information_system.helpers.config.yaml", read_yaml_config=lambda *a, **k: {})
    module("protein_information_system.helpers.services.services", check_services=lambda *a, **k: None)
    module("fantasia.src.embedder", SequenceEmbedder=object)
    module("fantasia.src.lookup", EmbeddingLookUp=object)

    def download(url, tar_path):
        download_calls.append((url, tar_path))
        return Path(tar_path)

    module(
        "fantasia.src.helpers.helpers",
        download_embeddings=download,
        load_dump_to_db=lambda *a, **k: load_dump_result,
        parse_unknown_args=lambda *a, **k: {},
    )
    sys.modules.pop("fantasia.main", None)
    return importlib.import_module("fantasia.main")


def test_initialize_raises_when_restore_fails(monkeypatch, tmp_path):
    calls = []
    main = _load_main(monkeypatch, load_dump_result=False, download_calls=calls)
    conf = {"base_directory": str(tmp_path), "embeddings_url": "https://example.org/ref.backup?download=1"}

    with pytest.raises(RuntimeError, match="Could not load the reference dump"):
        main.initialize(conf)
    assert calls[0][1] == str(tmp_path / "embeddings" / "ref.backup")


def test_initialize_succeeds_when_restore_succeeds(monkeypatch, tmp_path):
    main = _load_main(monkeypatch, load_dump_result=True, download_calls=[])
    main.initialize({"base_directory": str(tmp_path), "embeddings_url": "https://example.org/ref.backup"})


def test_cli_initialize_exits_non_zero_on_failure(monkeypatch, tmp_path):
    main = _load_main(monkeypatch, load_dump_result=False, download_calls=[])
    conf = {"base_directory": str(tmp_path), "embeddings_url": "https://example.org/ref.backup",
            "log_path": str(tmp_path / "logs")}
    monkeypatch.setattr(main, "build_parser", lambda: SimpleNamespace(
        parse_known_args=lambda: (SimpleNamespace(command="initialize"), [])))
    monkeypatch.setattr(main, "load_and_merge_config", lambda args, unknown: dict(conf))
    monkeypatch.setattr(main, "setup_logger", lambda *a, **k: logging.getLogger("test"))

    with pytest.raises(SystemExit) as excinfo:
        main.main()
    assert excinfo.value.code == 1


def test_postgres_client_encoding_defaults_to_utf8(monkeypatch):
    monkeypatch.delenv("PGCLIENTENCODING", raising=False)
    _load_main(monkeypatch, load_dump_result=True, download_calls=[])
    import os
    assert os.environ["PGCLIENTENCODING"] == "UTF8"
