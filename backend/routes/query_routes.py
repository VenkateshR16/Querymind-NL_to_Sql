from flask import Blueprint, request, jsonify
from models.flan_t5 import sql_generator
from models.whisper_asr import asr
from models.ocr_engine import ocr
from services.duckdb_service import db_service
from services.validator import validate_sql
from services.history_service import save_query
from services.column_advisor import column_advisor

query_bp = Blueprint('query', __name__)

def _run_query(question: str, table_names, input_mode: str) -> tuple:
    # Accept single string or list
    if isinstance(table_names, str):
        table_names = [t.strip() for t in table_names.split(',') if t.strip()]

    loaded = db_service.get_tables()
    for t in table_names:
        if t not in loaded:
            return {"error": f"Table '{t}' not loaded. Upload it first."}, 400

    # Generate SQL
    if len(table_names) == 1:
        schema = db_service.get_schema(table_names[0])
        sql = sql_generator.generate_sql(question, schema, table_names[0])
    else:
        sql = sql_generator.generate_multi_sql(question, table_names, db_service)

    # Validate
    validation = validate_sql(sql)
    if not validation['valid']:
        save_query(question, sql, ','.join(table_names), 0, 0, input_mode, 'failed', validation['error'])
        return {"error": validation['error'], "raw_sql": sql}, 400

    # Execute
    result = db_service.execute_query(validation['formatted'])
    status = 'success' if result['success'] else 'failed'
    save_query(question, validation['formatted'], ','.join(table_names),
               result.get('row_count', 0), result.get('elapsed_ms', 0),
               input_mode, status, result.get('error'))

    # Column recommendations (use first table for now)
    cols = db_service.get_schema_list(table_names[0])
    recommendations = column_advisor.recommend(question, cols)

    return {
        "success": result['success'],
        "question": question,
        "sql": validation['formatted'],
        "tables": table_names,
        "result": {k: v for k, v in result.items() if k != 'dataframe'},
        "recommendations": recommendations,
    }, 200 if result['success'] else 400


@query_bp.route('/text', methods=['POST'])
def query_from_text():
    data = request.get_json(force=True)
    question   = data.get('question', '').strip()
    table_name = data.get('table_name', '').strip()
    tables     = data.get('tables', None)
    if tables:
        table_names = tables if isinstance(tables, list) else [t.strip() for t in tables.split(',')]
    else:
        table_names = table_name
    if not question:
        return jsonify({"error": "Question is required"}), 400
    if not table_names:
        return jsonify({"error": "table_name or tables is required"}), 400
    resp, code = _run_query(question, table_names, 'text')
    return jsonify(resp), code


@query_bp.route('/voice', methods=['POST'])
def query_from_voice():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400
    table_name = request.form.get('table_name', '').strip()
    tables     = request.form.get('tables', '').strip()
    # FIX: wrap table_name in a list instead of passing raw string
    table_names = [t.strip() for t in tables.split(',')] if tables else ([table_name] if table_name else [])
    if not table_names:
        return jsonify({"error": "table_name or tables is required"}), 400
    audio_file = request.files['audio']
    asr_result = asr.transcribe(audio_file.read(), audio_file.filename or 'audio.webm')
    if not asr_result['success']:
        return jsonify({"error": asr_result['error'], "asr_available": False}), 400
    question = asr_result['text']
    if not question:
        return jsonify({"error": "No speech detected"}), 400
    resp, code = _run_query(question, table_names, 'voice')
    if isinstance(resp, dict):
        resp['transcription'] = question
    return jsonify(resp), code


@query_bp.route('/image', methods=['POST'])
def query_from_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file uploaded"}), 400
    table_name = request.form.get('table_name', '').strip()
    tables     = request.form.get('tables', '').strip()
    # FIX: wrap table_name in a list instead of passing raw string
    table_names = [t.strip() for t in tables.split(',')] if tables else ([table_name] if table_name else [])
    if not table_names:
        return jsonify({"error": "table_name or tables is required"}), 400
    image_file = request.files['image']
    ocr_result = ocr.extract_text(image_file.read())
    if not ocr_result['success']:
        return jsonify({"error": ocr_result['error'], "ocr_available": False}), 400
    question = ocr_result['text']
    if not question:
        return jsonify({"error": "No text detected in image"}), 400
    resp, code = _run_query(question, table_names, 'image')
    if isinstance(resp, dict):
        resp['extracted_text'] = question
    return jsonify(resp), code


@query_bp.route('/direct', methods=['POST'])
def run_direct_sql():
    data = request.get_json(force=True)
    sql  = data.get('sql', '').strip()
    table_name = data.get('table_name', 'direct')
    if not sql:
        return jsonify({"error": "SQL is required"}), 400
    validation = validate_sql(sql)
    if not validation['valid']:
        return jsonify({"error": validation['error']}), 400
    result = db_service.execute_query(validation['formatted'])
    save_query('[Direct SQL]', validation['formatted'], table_name,
               result.get('row_count', 0), result.get('elapsed_ms', 0), 'direct',
               'success' if result['success'] else 'failed', result.get('error'))
    return jsonify({
        "success": result['success'],
        "sql": validation['formatted'],
        "result": {k: v for k, v in result.items() if k != 'dataframe'}
    }), 200 if result['success'] else 400


@query_bp.route('/tables', methods=['GET'])
def get_tables():
    tables = db_service.get_tables()
    info = {t: db_service.get_table_info(t) for t in tables}
    return jsonify({"tables": tables, "info": info})


@query_bp.route('/join-hint', methods=['POST'])
def join_hint():
    """Returns common columns between two tables for JOIN preview."""
    data = request.get_json(force=True)
    t1 = data.get('table1', '')
    t2 = data.get('table2', '')
    if not t1 or not t2:
        return jsonify({"error": "table1 and table2 required"}), 400
    common = db_service.get_common_columns(t1, t2)
    return jsonify({"common_columns": common, "can_join": len(common) > 0})