from flask import Blueprint, request, jsonify
from services.history_service import get_history, delete_history_item, clear_history, get_stats

history_bp = Blueprint('history', __name__)

@history_bp.route('/', methods=['GET'])
def list_history():
    limit = int(request.args.get('limit', 50))
    table = request.args.get('table')
    items = get_history(limit=limit, table_name=table)
    return jsonify({"items": items, "count": len(items)})

@history_bp.route('/stats', methods=['GET'])
def history_stats():
    return jsonify(get_stats())

@history_bp.route('/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    ok = delete_history_item(item_id)
    return jsonify({"success": ok})

@history_bp.route('/clear', methods=['DELETE'])
def clear():
    ok = clear_history()
    return jsonify({"success": ok})
