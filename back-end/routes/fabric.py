"""Fabric intake v2: CostQuest delivery upload, the fabric status card, and
fabric-powered address search. Logic lives in services/fabric_service.py."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database.sessions import get_session
from services import fabric_service
from services.exceptions import ServiceError

bp = Blueprint("fabric", __name__)


@bp.route("/api/fabric/<int:folderid>", methods=["POST"])
@jwt_required()
def intake_fabric(folderid):
    identity = get_jwt_identity()
    session = get_session()
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify(
            {"status": "error", "message": "Attach the fabric delivery (a zip or CSV)"}
        ), 400
    override = request.form.get("override", "").lower() in ("1", "true", "yes")
    try:
        result = fabric_service.intake_fabric(
            identity["id"],
            folderid,
            upload.filename,
            upload.read(),
            session,
            override_vintage=override,
        )
        return jsonify({"status": "success", **result}), 200
    except ServiceError as e:
        session.rollback()
        return jsonify({"status": "error", "message": e.message}), e.status


@bp.route("/api/fabric/<int:folderid>", methods=["GET"])
@jwt_required()
def fabric_status(folderid):
    identity = get_jwt_identity()
    session = get_session()
    try:
        return jsonify(fabric_service.fabric_status(identity["id"], folderid, session)), 200
    except ServiceError as e:
        return jsonify({"status": "error", "message": e.message}), e.status


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
