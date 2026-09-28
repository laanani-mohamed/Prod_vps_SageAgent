"""
Dash/components/data_tables.py
"""
import streamlit as st
import pandas as pd
from typing import Optional

from core.formatters import format_date

_TIMESTAMP_RE = r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}"


def strip_time(df: pd.DataFrame) -> pd.DataFrame:
    """Tronque à YYYY-MM-DD les colonnes dont toutes les valeurs sont des horodatages."""
    out = None
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            new = s.dt.strftime("%Y-%m-%d")
        elif s.dtype == object or pd.api.types.is_string_dtype(s):
            txt = s.dropna().astype(str)
            txt = txt[txt != "-"]
            if txt.empty or not txt.str.match(_TIMESTAMP_RE).all():
                continue
            new = s.map(lambda v: format_date(str(v)) if pd.notna(v) else v)
        else:
            continue
        if out is None:
            out = df.copy()
        out[col] = new
    return df if out is None else out


def number_column_config(df: pd.DataFrame, width: Optional[str] = None) -> dict:
    """Colonnes décimales → séparateur de milliers + 2 décimales ; colonnes '%' → suffixe ' %'."""
    cfg = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            fmt = "%,.2f %%" if "%" in str(col) else "%,.2f"
            cfg[col] = st.column_config.NumberColumn(format=fmt, width=width)
    return cfg


def show_table(data, **kwargs):
    """st.dataframe (DataFrame ou Styler) avec le format numérique commun ; prime sur Styler.format."""
    if isinstance(data, pd.DataFrame):
        data = strip_time(data)
        df = data
    else:
        df = data.data
    cfg = number_column_config(df)
    cfg.update(kwargs.pop("column_config", None) or {})
    return st.dataframe(data, column_config=cfg, **kwargs)


def show_df(
    df: pd.DataFrame,
    hide_index: bool = True,
    on_select=None,
    selection_mode: str = "single-row",
    key_suffix: Optional[str] = None,
    height: Optional[int] = None,
):
    """
    Wrapper de st.dataframe qui utilise width='stretch' et key_suffix au lieu de id(df).
    """
    df = strip_time(df)
    col_cfg = {col: st.column_config.Column(width="small") for col in df.columns}
    col_cfg.update(number_column_config(df, width="small"))

    kwargs: dict = dict(
        data=df,
        width="stretch",
        hide_index=hide_index,
        column_config=col_cfg,
    )
    if height is not None:
        kwargs["height"] = height
    if on_select is not None:
        kwargs["on_select"] = on_select
        kwargs["selection_mode"] = selection_mode
    if key_suffix is not None:
        kwargs["key"] = f"table_{key_suffix}"

    return st.dataframe(**kwargs)
