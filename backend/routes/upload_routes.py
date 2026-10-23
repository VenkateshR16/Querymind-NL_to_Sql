import os
from flask import Blueprint, request, jsonify, current_app
from services.duckdb_service import db_service
from werkzeug.utils import secure_filename

upload_bp = Blueprint('upload', __name__)
ALLOWED = {'csv', 'tsv', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

@upload_bp.route('/csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only CSV/TSV files are supported"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    result = db_service.load_csv(save_path, filename)
    if not result['success']:
        return jsonify({"error": result['error']}), 400
    return jsonify(result)

@upload_bp.route('/tables', methods=['GET'])
def list_tables():
    tables = db_service.get_tables()
    info = {}
    for t in tables:
        ti = db_service.get_table_info(t)
        if ti:
            info[t] = {k: v for k, v in ti.items() if k != 'dataframe'}
    return jsonify({"tables": tables, "info": info})

@upload_bp.route('/schema/<table_name>', methods=['GET'])
def get_schema(table_name):
    if table_name not in db_service.get_tables():
        return jsonify({"error": "Table not found"}), 404
    schema_list = db_service.get_schema_list(table_name)
    stats = db_service.get_column_stats(table_name)
    preview = db_service._get_preview(table_name, 10)
    return jsonify({"columns": schema_list, "stats": stats, "preview": preview})
