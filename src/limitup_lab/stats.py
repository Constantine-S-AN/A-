from __future__ import annotations

import pandas as pd


DEFAULT_GROUP_COLUMNS = ["board", "is_st", "streak_up", "one_word", "opened"]
DEFAULT_RETURN_COLUMNS = ["next_open_ret", "next_close_ret"]
GROUP_COLUMN_ALIASES = {
    "one_word": "label_one_word",
    "opened": "label_opened",
}


def _materialize_group_columns(dataframe: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    grouped_frame = dataframe.copy()
    missing_columns: list[str] = []
    for column_name in by:
        if column_name in grouped_frame.columns:
            continue
        alias_column = GROUP_COLUMN_ALIASES.get(column_name)
        if alias_column and alias_column in grouped_frame.columns:
            grouped_frame[column_name] = grouped_frame[alias_column]
            continue
        missing_columns.append(column_name)

    if missing_columns:
        raise ValueError(f"缺失分组列: {missing_columns}")
    return grouped_frame


def group_stats(
    dataframe: pd.DataFrame,
    by: list[str] | None = None,
    value_columns: list[str] | None = None,
) -> pd.DataFrame:
    group_columns = by or DEFAULT_GROUP_COLUMNS
    return_columns = value_columns or DEFAULT_RETURN_COLUMNS

    grouped_frame = _materialize_group_columns(dataframe, group_columns).copy()
    missing_return_columns = [
        column_name for column_name in return_columns if column_name not in grouped_frame.columns
    ]
    if missing_return_columns:
        raise ValueError(f"缺失收益列: {missing_return_columns}")

    for column_name in return_columns:
        grouped_frame[column_name] = pd.to_numeric(grouped_frame[column_name], errors="coerce")

    grouped_frame = grouped_frame.loc[grouped_frame[return_columns].notna().any(axis=1)].copy()
    if grouped_frame.empty:
        metric_columns = [
            f"{column_name}_{metric_name}"
            for column_name in return_columns
            for metric_name in ("mean", "p10", "p50", "p90")
        ]
        return pd.DataFrame(columns=[*group_columns, "count", *metric_columns])

    grouped = grouped_frame.groupby(group_columns, dropna=False, sort=True)
    summary = grouped.size().rename("count").reset_index()

    for column_name in return_columns:
        mean_stats = grouped[column_name].mean().rename(f"{column_name}_mean")
        quantile_stats = grouped[column_name].quantile([0.1, 0.5, 0.9]).unstack(level=-1)
        quantile_stats = quantile_stats.rename(
            columns={
                0.1: f"{column_name}_p10",
                0.5: f"{column_name}_p50",
                0.9: f"{column_name}_p90",
            }
        )
        column_stats = pd.concat([mean_stats, quantile_stats], axis=1).reset_index()
        summary = summary.merge(column_stats, on=group_columns, how="left")

    return summary.sort_values(group_columns).reset_index(drop=True)

