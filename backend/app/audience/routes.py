"""Public API for the pDOOH audience engine."""
from flask import Blueprint, jsonify, request
from .engine import simulate

audience_bp = Blueprint('audience', __name__)

@audience_bp.post('/run')
def run():
    try:
        return jsonify(success=True, data=simulate(request.get_json(silent=True)))
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400
