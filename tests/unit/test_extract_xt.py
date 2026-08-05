"""Unit tests for extract_xt's pure grid helpers. No network calls."""

from statsbomb.extract_xt import XT_GRID, _GRID_COLS, _GRID_ROWS, _map_to_zone, build_grid_json


class TestGridShape:
    def test_grid_has_configured_row_count(self):
        assert len(XT_GRID) == _GRID_ROWS == 8

    def test_every_row_has_configured_col_count(self):
        assert all(len(row) == _GRID_COLS == 12 for row in XT_GRID)


class TestMapToZone:
    def test_origin_maps_to_first_cell(self):
        assert _map_to_zone(0.0, 0.0) == (0, 0)

    def test_upper_bound_clamps_to_last_cell(self):
        # x=120, y=80 are the exact pitch-edge values StatsBomb can emit —
        # naive int(x/width*cols) would compute col=12, one past the last
        # valid index (11). Must clamp, not index out of range.
        assert _map_to_zone(120.0, 80.0) == (_GRID_ROWS - 1, _GRID_COLS - 1)

    def test_just_inside_the_last_cell(self):
        assert _map_to_zone(119.9, 79.9) == (_GRID_ROWS - 1, _GRID_COLS - 1)

    def test_a_middle_point(self):
        # x=60 -> col index 6 of 12 (60/120*12 = 6.0); y=40 -> row index 4 of 8
        # (40/80*8 = 4.0).
        assert _map_to_zone(60.0, 40.0) == (4, 6)

    def test_zone_indices_are_always_in_range(self):
        for row, col in _map_to_zone(120.0, 80.0), _map_to_zone(0.0, 0.0):
            assert 0 <= row < _GRID_ROWS
            assert 0 <= col < _GRID_COLS


class TestBuildGridJson:
    def test_contract_keys(self):
        grid = build_grid_json()
        assert set(grid.keys()) == {
            "rows", "cols", "values", "source", "source_url", "pitch_dims", "cell_dims",
        }

    def test_dimensions_match_the_grid_constants(self):
        grid = build_grid_json()
        assert grid["rows"] == _GRID_ROWS
        assert grid["cols"] == _GRID_COLS
        assert len(grid["values"]) == _GRID_ROWS
        assert all(len(row) == _GRID_COLS for row in grid["values"])
