import io
import pandas as pd
from fpdf import FPDF
import datetime


def _format_numeric_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Round and format all numeric columns to 2 decimal places for export."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]) or pd.api.types.is_integer_dtype(df[col]):
            # Keep numeric but rounded to 2 decimals
            df[col] = df[col].apply(lambda x: round(float(x), 2) if pd.notnull(x) else x)
    return df


def export_df_to_excel(df: pd.DataFrame) -> bytes:
    """Export a DataFrame to Excel with numeric columns formatted to 2 decimal places."""
    df_export = _format_numeric_cols(df)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Report')
        # Apply number format to numeric columns
        ws = writer.sheets['Report']
        for col_idx, col_name in enumerate(df_export.columns, start=1):
            if pd.api.types.is_float_dtype(df_export[col_name]) or pd.api.types.is_integer_dtype(df_export[col_name]):
                for row_idx in range(2, len(df_export) + 2):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    cell.number_format = '#,##0.00'
    processed_data = output.getvalue()
    return processed_data


def _safe_pdf_text(value) -> str:
    """Convertit une valeur en texte PDF propre et sans caractères parasites."""
    text = "" if value is None else str(value)
    return text.replace("?", "").replace("\n", " ").strip()


def export_df_to_pdf(df: pd.DataFrame, title: str, subtitle: str = "") -> bytes:
    """Export a DataFrame to a simple PDF table with numeric values at 2 decimal places."""
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()

    clean_title = _safe_pdf_text(title) or "Rapport"
    clean_subtitle = _safe_pdf_text(subtitle)

    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 10, txt=clean_title.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
    pdf.ln(2)

    if clean_subtitle:
        pdf.set_font("Arial", style='I', size=11)
        pdf.cell(0, 8, txt=clean_subtitle.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
        pdf.ln(2)

    pdf.set_font("Arial", size=9)
    pdf.cell(0, 8, txt=f"Genere le: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='L')
    pdf.ln(4)

    if not df.empty:
        col_names = df.columns.tolist()
        page_width = pdf.w - 2 * pdf.l_margin

        col_max_lens = []
        for col in col_names:
            max_len = len(str(col))
            for item in df[col]:
                if isinstance(item, float):
                    item_str = f"{item:,.2f}"
                elif isinstance(item, int) and col not in ["Nb Factures", "Code", "Code Collab."]:
                    item_str = f"{item:,.2f}"
                else:
                    item_str = str(item)
                max_len = max(max_len, len(item_str))
            col_max_lens.append(max_len)

        total_len = sum(col_max_lens) or 1
        col_widths = [max((w / total_len) * page_width, 10.0) for w in col_max_lens]
        current_total = sum(col_widths)
        col_widths = [(w / current_total) * page_width for w in col_widths]

        pdf.set_fill_color(41, 128, 185)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", style='B', size=8)
        for col, width in zip(col_names, col_widths):
            header_text = str(col).encode('latin-1', 'replace').decode('latin-1')[:40]
            pdf.cell(width, 8, header_text, border=1, align='C', fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Arial", size=7)
        for _, row in df.iterrows():
            for col_name, width, item in zip(col_names, col_widths, row):
                if isinstance(item, float):
                    formatted = f"{item:,.2f}"
                elif isinstance(item, int) and col_name not in ["Nb Factures", "Code", "Code Collab."]:
                    formatted = f"{item:,.2f}"
                else:
                    formatted = str(item)
                cell_text = formatted.encode('latin-1', 'replace').decode('latin-1')[:50]
                pdf.cell(width, 7, cell_text, border=1, align='C')
            pdf.ln()

    pdf_string = pdf.output(dest='S').encode('latin-1', 'replace')
    return pdf_string


def export_visite_to_pdf(sections: list, title: str, subtitle: str = "") -> bytes:
    """
    Export multi-section rapport to PDF — one table per section with title separator.
    sections: list of (section_title, DataFrame)
    """
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Main title
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 10, txt=_safe(title), ln=True, align='C')
    pdf.ln(2)

    if subtitle:
        pdf.set_font("Arial", style='I', size=11)
        pdf.cell(0, 8, txt=_safe(subtitle), ln=True, align='C')
        pdf.ln(2)

    pdf.set_font("Arial", size=9)
    pdf.cell(0, 8, txt=f"Genere le: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='L')
    pdf.ln(4)

    page_width = pdf.w - 2 * pdf.l_margin

    for section_title, df in sections:
        # Check if we need a new page (at least 40mm needed for title + header + 1 row)
        if pdf.get_y() > pdf.h - 50:
            pdf.add_page()

        # Section title with colored background
        pdf.set_fill_color(41, 128, 185)  # blue
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", style='B', size=11)
        pdf.cell(page_width, 9, txt=_safe(section_title), border=0, ln=True, align='L', fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        if df is None or df.empty:
            pdf.set_font("Arial", style='I', size=9)
            pdf.cell(page_width, 8, txt="Aucune donnee.", ln=True, align='L')
            pdf.ln(6)
            continue

        col_names = df.columns.tolist()

        # Column widths — proportional to max content length
        col_max_lens = []
        for col in col_names:
            max_len = len(str(col))
            for item in df[col]:
                if isinstance(item, float):
                    s = f"{item:,.2f}"
                elif isinstance(item, int):
                    s = f"{item:,.2f}"
                else:
                    s = str(item)
                max_len = max(max_len, len(s))
            col_max_lens.append(max_len)

        total_len = sum(col_max_lens) or 1
        col_widths = [max((w / total_len) * page_width, 10.0) for w in col_max_lens]
        current_total = sum(col_widths)
        col_widths = [(w / current_total) * page_width for w in col_widths]

        # Header row
        pdf.set_font("Arial", style='B', size=8)
        pdf.set_fill_color(220, 220, 220)
        for col, width in zip(col_names, col_widths):
            pdf.cell(width, 8, _safe(str(col))[:40], border=1, align='C', fill=True)
        pdf.ln()

        # Data rows
        pdf.set_font("Arial", size=7)
        for _, row in df.iterrows():
            # Page break check per row
            if pdf.get_y() > pdf.h - 20:
                pdf.add_page()
                # Re-print header on new page
                pdf.set_font("Arial", style='B', size=8)
                pdf.set_fill_color(220, 220, 220)
                for col, width in zip(col_names, col_widths):
                    pdf.cell(width, 8, _safe(str(col))[:40], border=1, align='C', fill=True)
                pdf.ln()
                pdf.set_font("Arial", size=7)

            for col_name, width, item in zip(col_names, col_widths, row):
                if isinstance(item, float):
                    formatted = f"{item:,.2f}"
                elif isinstance(item, int):
                    formatted = f"{item:,.2f}"
                else:
                    formatted = str(item)
                pdf.cell(width, 7, _safe(formatted)[:50], border=1, align='C')
            pdf.ln()

        pdf.ln(6)

    return pdf.output(dest='S').encode('latin-1', 'replace')
