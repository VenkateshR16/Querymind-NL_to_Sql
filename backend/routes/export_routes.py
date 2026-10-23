from flask import Blueprint, request, jsonify, send_file
from services.export_service import export_to_csv, export_to_pdf, export_chart_png
import io, datetime

export_bp = Blueprint('export', __name__)

@export_bp.route('/csv', methods=['POST'])
def export_csv():
    data = request.get_json(force=True)
    rows = data.get('rows', [])
    columns = data.get('columns', [])
    if not rows:
        return jsonify({"error": "No data to export"}), 400
    csv_bytes = export_to_csv(rows, columns)
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'querymind_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@export_bp.route('/pdf', methods=['POST'])
def export_pdf():
    data = request.get_json(force=True)
    rows = data.get('rows', [])
    columns = data.get('columns', [])
    question = data.get('question', 'Query Result')
    sql = data.get('sql', '')
    table_name = data.get('table_name', '')
    if not rows:
        return jsonify({"error": "No data to export"}), 400
    pdf_bytes = export_to_pdf(rows, columns, question, sql, table_name)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'querymind_report_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

@export_bp.route('/chart', methods=['POST'])
def export_chart():
    data = request.get_json(force=True)
    rows = data.get('rows', [])
    chart_hint = data.get('chart_hint', {})
    question = data.get('question', 'Query Result')
    if not rows:
        return jsonify({"error": "No data to chart"}), 400
    png_bytes = export_chart_png(rows, chart_hint, question)
    if not png_bytes:
        return jsonify({"error": "Could not generate chart"}), 400
    return send_file(
        io.BytesIO(png_bytes),
        mimetype='image/png',
        as_attachment=True,
        download_name=f'querymind_chart_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    )
