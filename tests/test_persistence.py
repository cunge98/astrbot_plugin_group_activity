"""
Tests for data persistence: _load, _save (debounce), _force_save.
"""
import json
import time
import pytest
from unittest.mock import MagicMock, patch


class TestLoad:

    def test_returns_empty_structure_when_no_file(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "nonexistent.json"
        result = plugin._load()
        assert result == {"groups": {}}

    def test_loads_valid_json(self, plugin, tmp_path):
        data = {"groups": {"123": {"members": {"456": {"last_active": 9999}}}}}
        f = tmp_path / "data.json"
        f.write_text(json.dumps(data), "utf-8")
        plugin.data_file = f
        assert plugin._load() == data

    def test_returns_empty_structure_on_corrupt_json(self, plugin, tmp_path):
        f = tmp_path / "corrupt.json"
        f.write_text("not { valid json !!!", "utf-8")
        plugin.data_file = f
        result = plugin._load()
        assert result == {"groups": {}}

    def test_returns_empty_structure_on_empty_file(self, plugin, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("", "utf-8")
        plugin.data_file = f
        result = plugin._load()
        assert result == {"groups": {}}

    def test_unicode_data_roundtrip(self, plugin, tmp_path):
        data = {"groups": {"123": {"group_name": "测试群", "members": {}}}}
        f = tmp_path / "unicode.json"
        f.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        plugin.data_file = f
        loaded = plugin._load()
        assert loaded["groups"]["123"]["group_name"] == "测试群"


class TestForceSave:

    def test_writes_data_to_disk(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "out.json"
        plugin.activity_data = {"groups": {"111": {"members": {}}}}
        plugin._force_save()
        on_disk = json.loads(plugin.data_file.read_text("utf-8"))
        assert on_disk == {"groups": {"111": {"members": {}}}}

    def test_clears_dirty_flag(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "out.json"
        plugin._dirty = True
        plugin.activity_data = {"groups": {}}
        plugin._force_save()
        assert plugin._dirty is False

    def test_updates_last_save_timestamp(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "out.json"
        plugin.activity_data = {"groups": {}}
        before = time.time()
        plugin._force_save()
        after = time.time()
        assert before <= plugin._last_save <= after

    def test_preserves_unicode(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "out.json"
        plugin.activity_data = {"groups": {"1": {"group_name": "你好世界", "members": {}}}}
        plugin._force_save()
        raw = plugin.data_file.read_text("utf-8")
        assert "你好世界" in raw


class TestSaveDebounce:

    def test_save_writes_immediately_when_interval_elapsed(self, plugin, tmp_path):
        plugin.data_file = tmp_path / "out.json"
        plugin.activity_data = {"groups": {}}
        plugin._last_save = time.time() - 60   # 60 s ago, > 30 s interval

        mock_force = MagicMock()
        plugin._force_save = mock_force
        plugin._save()

        mock_force.assert_called_once()

    def test_save_defers_when_recently_saved(self, plugin):
        plugin._last_save = time.time()   # just saved
        plugin._dirty = False

        mock_force = MagicMock()
        plugin._force_save = mock_force
        plugin._save()

        mock_force.assert_not_called()
        assert plugin._dirty is True

    def test_dirty_flag_flushed_in_loop(self, plugin, tmp_path):
        """Simulates the loop noticing _dirty=True and calling _force_save."""
        plugin.data_file = tmp_path / "out.json"
        plugin.activity_data = {"groups": {}}
        plugin._dirty = True
        plugin._last_save = time.time()   # recent, so _save() would defer

        # The loop logic: if dirty, force-save
        if plugin._dirty:
            plugin._force_save()

        assert plugin._dirty is False
        assert plugin.data_file.exists()
