"""Configuration tests."""

from pyslow.config import SLOWRENJU_PARA, adjust_loaded_parameters, load_default_config
from pyslow.constants import DSHAPE_SIZE


def test_slowrenju_parameter_count() -> None:
    assert len(SLOWRENJU_PARA) == 375


def test_parameter_slices_have_expected_lengths() -> None:
    config = load_default_config()
    assert len(config.eval_tables.last_eval) == DSHAPE_SIZE
    assert len(config.eval_tables.next_eval) == DSHAPE_SIZE
    assert len(config.eval_tables.attack_value) == DSHAPE_SIZE
    assert len(config.eval_tables.defend_value) == DSHAPE_SIZE


def test_parameter_boundaries_match_reference_offsets() -> None:
    config = load_default_config()
    assert config.eval_tables.last_eval[0] == SLOWRENJU_PARA[0]
    assert config.eval_tables.last_eval[-1] == SLOWRENJU_PARA[DSHAPE_SIZE - 1]
    assert config.eval_tables.next_eval[0] == SLOWRENJU_PARA[DSHAPE_SIZE]
    assert config.eval_tables.attack_value[0] == SLOWRENJU_PARA[DSHAPE_SIZE * 2]
    assert config.eval_tables.defend_value[0] == SLOWRENJU_PARA[DSHAPE_SIZE * 3]
    assert config.search.drift == SLOWRENJU_PARA[DSHAPE_SIZE * 4]
    assert config.search.extend_ratio == SLOWRENJU_PARA[DSHAPE_SIZE * 4 + 6]


def test_read_config_flag_defaults_to_false() -> None:
    config = load_default_config()
    assert config.runtime.read_config_each_move is False


def test_root_search_defaults_match_reference_entry() -> None:
    config = load_default_config()
    assert config.root_search.depth == 24
    assert config.root_search.wide == 60
    assert config.root_search.ratio_num == 1
    assert config.root_search.ratio_den == 1


def test_runtime_defaults_match_reference_behavior() -> None:
    config = load_default_config()
    assert config.runtime.compute_vcf is True
    assert config.runtime.static_board is True
    assert config.runtime.dynamic_board_margin == 4


def test_loaded_parameter_adjustments_match_reference() -> None:
    adjusted = adjust_loaded_parameters(SLOWRENJU_PARA)
    assert adjusted[156] == SLOWRENJU_PARA[156] + 65536.0
    assert adjusted[157] == SLOWRENJU_PARA[157] + 65536.0
