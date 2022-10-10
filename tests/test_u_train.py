from splink.duckdb.duckdb_comparison_library import levenshtein_at_thresholds
from splink.duckdb.duckdb_linker import DuckDBLinker
import pandas as pd
import numpy as np
from splink.comparison_level_library import _mutable_params

from pytest import approx


def test_u_train():

    data = [
        {"unique_id": 1, "name": "Amanda"},
        {"unique_id": 2, "name": "Robin"},
        {"unique_id": 3, "name": "Robyn"},
        {"unique_id": 4, "name": "David"},
        {"unique_id": 5, "name": "Eve"},
        {"unique_id": 6, "name": "Amanda"},
    ]
    df = pd.DataFrame(data)

    _mutable_params["dialect"] = "duckdb"
    settings = {
        "link_type": "dedupe_only",
        "comparisons": [levenshtein_at_thresholds("name", 2)],
        "blocking_rules_to_generate_predictions": ["l.name = r.name"],
    }

    linker = DuckDBLinker(df, settings)
    linker.debug_mode = True
    linker.estimate_u_using_random_sampling(target_rows=1e6)
    cc_name = linker._settings_obj.comparisons[0]

    denom = (6 * 5) / 2  # n(n-1) / 2
    cl_exact = cc_name._get_comparison_level_by_comparison_vector_value(2)
    assert cl_exact.u_probability == 1 / denom
    cl_lev = cc_name._get_comparison_level_by_comparison_vector_value(1)
    assert cl_lev.u_probability == 1 / denom
    cl_no = cc_name._get_comparison_level_by_comparison_vector_value(0)
    assert cl_no.u_probability == (denom - 2) / denom

    br = linker._settings_obj._blocking_rules_to_generate_predictions[0]
    assert br.blocking_rule == "l.name = r.name"


def test_u_train_link_only():

    data_l = [
        {"unique_id": 1, "name": "Amanda"},
        {"unique_id": 2, "name": "Robin"},
        {"unique_id": 3, "name": "Robyn"},
        {"unique_id": 4, "name": "David"},
        {"unique_id": 5, "name": "Eve"},
        {"unique_id": 6, "name": "Amanda"},
        {"unique_id": 7, "name": "Stuart"},
    ]
    data_r = [
        {"unique_id": 1, "name": "Eva"},
        {"unique_id": 2, "name": "David"},
        {"unique_id": 3, "name": "Sophie"},
        {"unique_id": 4, "name": "Jimmy"},
        {"unique_id": 5, "name": "Stuart"},
        {"unique_id": 6, "name": "Jimmy"},
    ]
    df_l = pd.DataFrame(data_l)
    df_r = pd.DataFrame(data_r)

    _mutable_params["dialect"] = "duckdb"
    settings = {
        "link_type": "link_only",
        "comparisons": [levenshtein_at_thresholds("name", 2)],
        "blocking_rules_to_generate_predictions": [],
    }

    linker = DuckDBLinker([df_l, df_r], settings)
    linker.debug_mode = True
    linker.estimate_u_using_random_sampling(target_rows=1e6)
    cc_name = linker._settings_obj.comparisons[0]

    check_blocking_sql = """
    SELECT COUNT(*) AS count FROM __splink__df_blocked
    WHERE source_dataset_l = source_dataset_r
    """
    self_table_count = linker._sql_to_splink_dataframe_checking_cache(
        check_blocking_sql, "__splink__df_blocked_same_table_count"
    )

    result = self_table_count.as_record_dict()
    print(result)
    self_table_count.drop_table_from_database()
    assert result[0]["count"] == 0

    denom = 6 * 7  # only l <-> r candidate links
    cl_exact = cc_name._get_comparison_level_by_comparison_vector_value(2)
    # David, Stuart
    assert cl_exact.u_probability == 2 / denom
    # Eve/Eva
    cl_lev = cc_name._get_comparison_level_by_comparison_vector_value(1)
    assert cl_lev.u_probability == 1 / denom
    cl_no = cc_name._get_comparison_level_by_comparison_vector_value(0)
    assert cl_no.u_probability == (denom - 3) / denom


def test_u_train_link_only_sample():

    df_l = (
        pd.DataFrame(np.random.randint(0, 1000, size=(1000, 1)), columns=["name"])
        .reset_index()
        .rename(columns={"index": "unique_id"})
    )
    df_r = (
        pd.DataFrame(np.random.randint(0, 1000, size=(1000, 1)), columns=["name"])
        .reset_index()
        .rename(columns={"index": "unique_id"})
    )

    target_rows = 100000

    _mutable_params["dialect"] = "duckdb"
    settings = {
        "link_type": "link_only",
        "comparisons": [levenshtein_at_thresholds("name", 2)],
        "blocking_rules_to_generate_predictions": [],
    }

    linker = DuckDBLinker([df_l, df_r], settings)
    linker.debug_mode = True
    linker.estimate_u_using_random_sampling(target_rows=target_rows)
    cc_name = linker._settings_obj.comparisons[0]

    check_blocking_sql = """
    SELECT COUNT(*) AS count FROM __splink__df_blocked
    """
    self_table_count = linker._sql_to_splink_dataframe_checking_cache(
        check_blocking_sql, "__splink__df_blocked_same_table_count"
    )

    result = self_table_count.as_record_dict()

    self_table_count.drop_table_from_database()
    target_rows_proportion = result[0]["count"] / target_rows
    # equality only holds probabilistically
    assert approx(target_rows_proportion, 0.1) == 1.0
