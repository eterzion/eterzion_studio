from fastapi import APIRouter, HTTPException

from app import authorizations, licensing, package_crypto, packages

router = APIRouter()


@router.get('/{name}/latest-version')
def get_latest_version(name: str):
    version = packages.latest_version(name)
    if version is None:
        raise HTTPException(404, f'Nenhuma versão de "{name}" foi construída ainda.')
    return {'name': name, 'version': version}


@router.get('/{name}')
def get_package(name: str, install_id: str, authorization_id: str):
    auth = authorizations.redeem_for_install(authorization_id, install_id)
    if auth is None:
        raise HTTPException(403, 'Autorização inválida, expirada, já utilizada, ou não pertence a esta instalação.')

    version = auth['version']
    built = packages.get_package(name, version)
    if built is None:
        raise HTTPException(404, f'Pacote "{name}" versão "{version}" não encontrado.')

    installation = licensing.get_installation(install_id)
    if installation is None:
        raise HTTPException(404, 'Instalação não encontrada.')

    wrap = package_crypto.wrap_content_key_for_install(built['content_key_b64'], installation['encryption_public_key_b64'])
    return {
        'name': name,
        'version': version,
        'ciphertext_b64': built['ciphertext_b64'],
        'nonce_b64': built['nonce_b64'],
        'signature_b64': built['signature_b64'],
        'key_wrap': wrap,
    }
