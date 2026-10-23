"""
Export service: CSV, PDF, PNG chart generation.
"""
import io, os, logging, json
from datetime import datetime

logger = logging.getLogger(__name__)

def export_to_csv(rows: list, columns: list) -> bytes:
    import pandas as pd
    df = pd.DataFrame(rows, columns=columns)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')

def export_to_pdf(rows: list, columns: list, question: str, sql: str, table_name: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                         Paragraph, Spacer, HRFlowable)
        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                 leftMargin=1.5*cm, rightMargin=1.5*cm,
                                 topMargin=1.5*cm, bottomMargin=1.5*cm)

        styles = getSampleStyleSheet()
        accent = colors.HexColor('#4F46E5')  # indigo
        dark   = colors.HexColor('#1E1B4B')

        title_style = ParagraphStyle('title', fontName='Helvetica-Bold',
                                      fontSize=18, textColor=dark, spaceAfter=4)
        meta_style  = ParagraphStyle('meta', fontName='Helvetica',
                                      fontSize=9, textColor=colors.HexColor('#6B7280'), spaceAfter=2)
        sql_style   = ParagraphStyle('sql', fontName='Courier', fontSize=8,
                                      textColor=colors.HexColor('#374151'),
                                      backColor=colors.HexColor('#F3F4F6'),
                                      borderPadding=(6, 10, 6, 10), spaceAfter=12)

        elements = []
        elements.append(Paragraph("QueryMind — Analytical Report", title_style))
        elements.append(Paragraph(f"Table: {table_name}  ·  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style))
        elements.append(Paragraph(f"Question: {question}", meta_style))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(HRFlowable(width="100%", thickness=1, color=accent))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(f"SQL: {sql}", sql_style))

        # Table
        display_rows = rows[:200]  # max 200 rows in PDF
        truncated = len(rows) > 200

        data = [columns] + [[str(row.get(c, '')) for c in columns] for row in display_rows]
        page_width = landscape(A4)[0] - 3*cm
        col_width = page_width / max(len(columns), 1)

        tbl = Table(data, colWidths=[col_width]*len(columns), repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',  (0,0), (-1,0), accent),
            ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
            ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0,0), (-1,0), 9),
            ('ALIGN',       (0,0), (-1,0), 'CENTER'),
            ('FONTNAME',    (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',    (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#F9FAFB')]),
            ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#E5E7EB')),
            ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',  (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ]))
        elements.append(tbl)

        if truncated:
            elements.append(Spacer(1, 0.3*cm))
            elements.append(Paragraph(f"⚠ Showing first 200 of {len(rows)} rows.", meta_style))

        doc.build(elements)
        buf.seek(0)
        return buf.read()

    except ImportError:
        return b"PDF export requires reportlab. Install with: pip install reportlab"

def export_chart_png(rows: list, chart_hint: dict, question: str) -> bytes:
    """Generate a PNG chart from query results."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd

        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("No data to chart")

        fig, ax = plt.subplots(figsize=(10, 6), facecolor='#FAFAFA')
        ax.set_facecolor('#FAFAFA')
        INDIGO = '#4F46E5'
        COLORS = ['#4F46E5','#7C3AED','#EC4899','#F59E0B','#10B981','#3B82F6','#EF4444']

        chart_type = chart_hint.get('type', 'bar')
        x_col = chart_hint.get('x')
        y_col = chart_hint.get('y')

        if chart_type == 'bar' and x_col and y_col and x_col in df and y_col in df:
            df_plot = df[[x_col, y_col]].dropna().head(15)
            bars = ax.bar(df_plot[x_col].astype(str), df_plot[y_col], color=INDIGO, alpha=0.85, width=0.6)
            ax.set_xlabel(x_col, fontsize=11)
            ax.set_ylabel(y_col, fontsize=11)
            plt.xticks(rotation=30, ha='right')
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x()+bar.get_width()/2, h*1.01, f'{h:,.0f}', ha='center', va='bottom', fontsize=8)

        elif chart_type == 'line' and x_col and y_col and x_col in df and y_col in df:
            df_plot = df[[x_col, y_col]].dropna()
            ax.plot(df_plot[x_col].astype(str), df_plot[y_col], color=INDIGO, linewidth=2, marker='o', markersize=5)
            ax.fill_between(range(len(df_plot)), df_plot[y_col], alpha=0.1, color=INDIGO)
            ax.set_xlabel(x_col, fontsize=11)
            ax.set_ylabel(y_col, fontsize=11)
            plt.xticks(rotation=30, ha='right')

        elif chart_type == 'pie':
            label_col = chart_hint.get('label')
            value_col = chart_hint.get('value')
            if label_col in df and value_col in df:
                df_plot = df[[label_col, value_col]].dropna().head(8)
                wedges, texts, autotexts = ax.pie(
                    df_plot[value_col], labels=df_plot[label_col].astype(str),
                    colors=COLORS[:len(df_plot)], autopct='%1.1f%%',
                    startangle=90, pctdistance=0.85
                )
                for t in autotexts: t.set_fontsize(9)

        elif chart_type == 'scatter' and x_col and y_col and x_col in df and y_col in df:
            ax.scatter(df[x_col], df[y_col], color=INDIGO, alpha=0.6, s=40)
            ax.set_xlabel(x_col, fontsize=11)
            ax.set_ylabel(y_col, fontsize=11)
        else:
            # Fallback: first two numeric columns
            num_df = df.select_dtypes(include='number')
            if len(num_df.columns) >= 1:
                num_df.iloc[:15, 0].plot(kind='bar', ax=ax, color=INDIGO, alpha=0.85)

        ax.set_title(question[:80] + ('...' if len(question) > 80 else ''), fontsize=12, pad=14, color='#1E1B4B')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(labelsize=9)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.error(f"Chart export error: {e}")
        return b""
