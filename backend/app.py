import os, sys
from flask import Flask, jsonify
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

from routes.query_routes import query_bp
from routes.upload_routes import upload_bp
from routes.history_routes import history_bp
from routes.export_routes import export_bp
from services.history_service import init_db

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.register_blueprint(query_bp,   url_prefix='/api/query')
app.register_blueprint(upload_bp,  url_prefix='/api/upload')
app.register_blueprint(history_bp, url_prefix='/api/history')
app.register_blueprint(export_bp,  url_prefix='/api/export')

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "File too large (max 50MB)"}), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500

if __name__ == '__main__':
    init_db()
    print("✅ QueryMind backend starting on http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
    logger.info(f"[EXECUTING SQL] {sql}")
