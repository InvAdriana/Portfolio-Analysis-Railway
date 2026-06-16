import io
import os
import streamlit as st

DRIVE_FILE_IDS = {
    "datos":         "1g8GYj_zU0BmfuRLf-Ts6WV2Eq6YFCWJw",
    "curvas_cobalt": "1pj4RInTUAFB-dlNQfgq02-xlPwfgGVmZ",
}

@st.cache_resource(show_spinner=False)
def _get_drive_service():
    """Crea cliente de Google Drive — lee credenciales de env vars (Railway) o secrets (Streamlit)."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if os.environ.get("GCP_PRIVATE_KEY"):
            creds_dict = {
                "type":           os.environ.get("GCP_TYPE", "service_account"),
                "project_id":     os.environ.get("GCP_PROJECT_ID"),
                "private_key_id": os.environ.get("GCP_PRIVATE_KEY_ID"),
                "private_key":    os.environ.get("GCP_PRIVATE_KEY", "").replace("\\n", "\n"),
                "client_email":   os.environ.get("GCP_CLIENT_EMAIL"),
                "client_id":      os.environ.get("GCP_CLIENT_ID"),
                "auth_uri":       "https://accounts.google.com/o/oauth2/auth",
                "token_uri":      "https://oauth2.googleapis.com/token",
            }
        else:
            try:
                creds_dict = dict(st.secrets["gcp_service_account"])
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            except Exception:
                raise RuntimeError(
                    "No se encontraron credenciales. "
                    "Define GCP_PRIVATE_KEY en las variables de entorno de Railway."
                )

        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)

    except Exception as e:
        # Mostrar error descriptivo en la UI
        st.error(f"❌ Error conectando a Google Drive: {e}")
        return None


def _get_file_id(key: str) -> str:
    env_map = {"datos": "DRIVE_DATOS_ID", "curvas_cobalt": "DRIVE_CURVAS_ID"}
    env_val = os.environ.get(env_map.get(key, ""))
    return env_val if env_val else DRIVE_FILE_IDS[key]


def load_excel_from_drive(file_key: str) -> io.BytesIO:
    """Descarga un Excel de Drive y lo devuelve como BytesIO."""
    file_id = _get_file_id(file_key)
    service = _get_drive_service()
    if service is None:
        raise RuntimeError(
            "No se pudo conectar a Google Drive. "
            "Revisa las variables GCP_* en Railway → Variables."
        )
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf
