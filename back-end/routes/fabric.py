"""Fabric intake v2: CostQuest delivery upload, the fabric status card, and
fabric-powered address search. Logic lives in services/fabric_service.py."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database.sessions import get_session
from services import fabric_service
from services.exceptions import ServiceError

bp = Blueprint("fabric", __name__)


@bp.route("/api/address-search/<int:folderid>", methods=["GET"])
@jwt_required()
def address_search(folderid):
    identity = get_jwt_identity()
    session = get_session()
    try:
        results = fabric_service.search_addresses(
            identity["id"], folderid, request.args.get("query", ""), session
        )
        return jsonify({"results": results}), 200
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status
