"""
components/date_filters.py

Filtre de dates unique du dashboard : deux st.date_input bornés à [date_min, date_max]
(dates réelles du document filtré) + garde-fou "date fin >= date début".
"""
import datetime
from typing import Optional

import streamlit as st

MSG_DATES_INVALIDES = "La date de fin doit être postérieure ou égale à la date de début."


def _clamp(d: Optional[datetime.date], lo: Optional[datetime.date], hi: Optional[datetime.date]):
    if d is None:
        return None
    if lo and d < lo:
        return lo
    if hi and d > hi:
        return hi
    return d


def date_range_filter(
    key_from: str,
    key_to: str,
    date_min: Optional[datetime.date],
    date_max: Optional[datetime.date],
    default_from: Optional[datetime.date] = None,
    default_to: Optional[datetime.date] = None,
    label_from: str = "Date début",
    label_to: str = "Date fin",
    cols=None,
) -> tuple[Optional[datetime.date], Optional[datetime.date], bool]:
    """Affiche le filtre et renvoie (date_from, date_to, ok) ; ok=False si fin < début (erreur affichée).

    Les dates par défaut sont ramenées dans les bornes ; si la période par défaut ne recoupe pas
    du tout les données, toute la période disponible est proposée. Une date gardée en session
    hors des bornes (ex. changement de client) est réinitialisée.
    """
    if (default_from and default_to and date_min and date_max
            and (default_from > date_max or default_to < date_min)):
        default_from, default_to = date_min, date_max

    col_from, col_to = cols if cols else st.columns(2)
    values = []
    for key, label, default, col in ((key_from, label_from, default_from, col_from),
                                     (key_to, label_to, default_to, col_to)):
        default = _clamp(default, date_min, date_max)
        current = st.session_state.get(key, default)
        if key not in st.session_state or _clamp(current, date_min, date_max) != current:
            st.session_state[key] = default
        # Sans `value`, Streamlit n'avertit pas d'un état fixé via session_state ;
        # value=None seulement pour un filtre vide par défaut (champ effaçable).
        extra = {"value": None} if default is None else {}
        with col:
            values.append(st.date_input(label, min_value=date_min, max_value=date_max, key=key, **extra))

    date_from, date_to = values
    ok = not (date_from and date_to and date_to < date_from)
    if not ok:
        st.error(MSG_DATES_INVALIDES)
    return date_from, date_to, ok
