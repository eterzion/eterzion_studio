"""T070 — GET /components, GET /components/{id}/details, install/update/delete
(contracts/api.md). Replaces GET /models (routes_models.py, removed below)
which returned raw model identifiers as `name` — a direct FR-009/FR-063
violation flagged by the analyze pass (G8) once video/audio content types
made "one row per file in astros_upscale.core.MODELS" stop matching "one
component per content type" (FR-095)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import component_manager
from app.core.component_manager import ComponentActionUnsupportedError, ComponentNotFoundError, ComponentInfo
from app.models.schemas import Component, ComponentDetails

router = APIRouter()


def _to_component(info: ComponentInfo) -> Component:
    return Component(
        id=info.id, capability_label=info.capability_label, size_mb=info.size_mb,
        install_state=info.install_state, update_available=info.update_available,
    )


def _to_details(info: ComponentInfo) -> ComponentDetails:
    return ComponentDetails(
        id=info.id, capability_label=info.capability_label, size_mb=info.size_mb,
        install_state=info.install_state, update_available=info.update_available,
        technical_name=info.technical_name, version=info.version, provenance=info.provenance,
        license=info.license,
    )


@router.get('', response_model=list[Component])
def list_components():
    return [_to_component(c) for c in component_manager.list_components()]


@router.get('/{component_id}/details', response_model=ComponentDetails)
def get_component_details(component_id: str):
    try:
        return _to_details(component_manager.get_component_details(component_id))
    except ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')


@router.post('/{component_id}/install', response_model=Component)
def install_component(component_id: str):
    try:
        return _to_component(component_manager.install_component(component_id))
    except ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')
    except ComponentActionUnsupportedError as error:
        raise HTTPException(422, str(error))


@router.post('/{component_id}/update', response_model=Component)
def update_component(component_id: str):
    try:
        return _to_component(component_manager.update_component(component_id))
    except ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')
    except ComponentActionUnsupportedError as error:
        raise HTTPException(422, str(error))


@router.delete('/{component_id}', response_model=Component)
def delete_component(component_id: str):
    try:
        return _to_component(component_manager.delete_component(component_id))
    except ComponentNotFoundError:
        raise HTTPException(404, 'Componente não encontrado.')
    except ComponentActionUnsupportedError as error:
        raise HTTPException(422, str(error))
