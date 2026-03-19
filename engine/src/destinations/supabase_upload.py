from ..storage.db import db


def upload_report(
    company_name: str,
    file_bytes: bytes,
    run_date: str,
    file_ext: str = "pdf",
    content_type: str = "application/pdf",
) -> str:
    """
    上传文件到 Supabase Storage 'reports' bucket。
    路径: {company}/{YYYY-MM-DD}.{ext}
    返回 7 天有效的签名 URL。
    """
    path = f"{company_name.lower()}/{run_date}.{file_ext}"

    db.storage.from_("reports").upload(
        path=path,
        file=bytes(file_bytes),
        file_options={"content-type": content_type, "upsert": "true"},
    )

    signed = db.storage.from_("reports").create_signed_url(path, 60 * 60 * 24 * 7)
    return signed.get("signedURL", "")
