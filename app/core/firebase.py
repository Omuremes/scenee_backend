import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import settings


def _initialize_firebase() -> None:
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    try:
        cred = credentials.Certificate("scenee-9fba8-firebase-adminsdk-fbsvc-8d3ea4e679.json")
        firebase_admin.initialize_app(cred)
    except FileNotFoundError:
        cred_dict = {
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
            "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n") if settings.FIREBASE_PRIVATE_KEY else None,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "client_id": settings.FIREBASE_CLIENT_ID,
            "auth_uri": settings.FIREBASE_AUTH_URI,
            "token_uri": settings.FIREBASE_TOKEN_URI,
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.FIREBASE_CLIENT_EMAIL}",
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)


_initialize_firebase()


async def verify_firebase_token(token: str) -> dict:
    try:
        return auth.verify_id_token(token, check_revoked=True)
    except Exception as exc:
        raise ValueError("Invalid Firebase token") from exc


def get_firebase_user(uid: str) -> dict:
    try:
        user = auth.get_user(uid)
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "email_verified": user.email_verified,
        }
    except Exception as exc:
        raise ValueError(f"Failed to get Firebase user: {str(exc)}") from exc
