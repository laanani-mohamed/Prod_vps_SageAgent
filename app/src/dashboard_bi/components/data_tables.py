"""
Dash/components/data_tables.py
"""
import streamlit as st
import pandas as pd
from typing import Optional

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
    col_cfg = {col: st.column_config.Column(width="small") for col in df.columns}

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
