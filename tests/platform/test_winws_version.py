"""Zapret version read/write in service.bat."""
import os
import tempfile

from src.entities.winws.winws_version import (
    read_local_version_from_winws_root,
    write_local_version_to_service,
    write_local_version_to_winws_root,
)


def test_write_and_read_local_version():
    with tempfile.TemporaryDirectory() as tmp:
        service_bat = os.path.join(tmp, "service.bat")
        with open(service_bat, "w", encoding="utf-8", newline="\n") as f:
            f.write('@echo off\nset "LOCAL_VERSION=1.9.9a"\n')
        assert write_local_version_to_service(service_bat, "1.9.9c") is True
        with open(service_bat, encoding="utf-8") as f:
            text = f.read()
        assert 'LOCAL_VERSION=1.9.9c' in text
        assert "1.9.9a" not in text


def test_read_local_version_prefers_zapret_latest_on_linux():
    with tempfile.TemporaryDirectory() as tmp:
        repo = os.path.join(tmp, "zapret-latest")
        os.makedirs(repo)
        with open(os.path.join(repo, "service.bat"), "w", encoding="utf-8") as f:
            f.write('set "LOCAL_VERSION=1.9.9c"\n')
        with open(os.path.join(tmp, "service.bat"), "w", encoding="utf-8") as f:
            f.write('set "LOCAL_VERSION=1.9.9a"\n')

        from unittest.mock import patch

        with patch("src.platform.is_linux", return_value=True):
            assert read_local_version_from_winws_root(tmp) == "1.9.9c"
            assert write_local_version_to_winws_root(tmp, "1.9.9d") is True
            assert read_local_version_from_winws_root(tmp) == "1.9.9d"
