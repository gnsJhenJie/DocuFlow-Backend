from fastapi import BackgroundTasks
from app.core.config import settings
import asyncio
import aioboto3

AWS_REGION = "ap-northeast-1"
CHARSET = "UTF-8"
SENDER = "docuflow@gnsjhenjie.ninja"


_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>Document Review Request</title>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; background:#F0F4F8; padding:24px;">
  <table style="max-width:600px;margin:auto;background:#ffffff;border-radius:8px;
               box-shadow:0 2px 6px rgba(0,0,0,.05);">
    <tr>
      <td style="padding:32px 32px 16px;">
        <h2 style="margin:0 0 8px;color:#333;">📝 A document needs your review</h2>
        <p style="margin:0;color:#555;">
          Hi {{reviewer_name}},<br/>
          <strong>{{author_name}}</strong> has submitted the document
          <strong>“{{doc_title}}”</strong> for your review.
        </p>
      </td>
    </tr>
    <tr>
      <td align="center" style="padding:16px 32px 32px;">
        <a href="{{doc_url}}" style="display:inline-block;padding:12px 24px;background:#64B5F6;
           color:#fff;text-decoration:none;border-radius:6px;font-weight:bold">
           Review now
        </a>
      </td>
    </tr>
    <tr>
      <td style="font-size:12px;color:#aaa;padding:0 32px 24px;text-align:center;">
        If the button doesn't work, copy the link below into your browser:<br/>
        <span style="word-break:break-all;">{{doc_url}}</span>
      </td>
    </tr>
  </table>
</body>
</html>
""".strip()

async def send_review_request_email(
    reviewer_email: str,
    reviewer_name: str,
    author_name: str,
    doc_title: str,
    doc_url: str,
):
    """非同步寄送『文件待審核』通知信"""
    session = aioboto3.Session()

    html_body = (
        _HTML_TEMPLATE.replace("{{reviewer_name}}", reviewer_name)
        .replace("{{author_name}}", author_name)
        .replace("{{doc_title}}", doc_title)
        .replace("{{doc_url}}", doc_url)
    )

    text_body = (
        f"Hi {reviewer_name},\n\n"
        f"{author_name} has submitted the document “{doc_title}” for your review.\n"
        f"Please open the link below to review it:\n{doc_url}\n\n"
        "— DocuFlow automated notification"
    )

    async with session.client(
            "ses", 
            region_name=AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        ) as ses:
        await ses.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [reviewer_email]},
            Message={
                "Subject": {"Charset": CHARSET, "Data": f'[DocuFlow] "{doc_title}" is awaiting your review'},
                "Body": {
                    "Text": {"Charset": CHARSET, "Data": text_body},
                    "Html": {"Charset": CHARSET, "Data": html_body},
                },
            },
        )



def queue_review_email(
    *,
    background_tasks: BackgroundTasks,
    reviewer_email: str,
    reviewer_name: str,
    author_name: str,
    doc_title: str,
    doc_id: int,
    frontend_url: str,
):
    """
    將「請 Reviewer 審核文件」的 email 寄送動作排入 BackgroundTasks。

    只收純值，避免 ORM detached；真正寄信時再用 asyncio.run()
    """
    doc_url = f"{frontend_url}/documents/view?id={doc_id}"

    def _fire():
        asyncio.run(
            send_review_request_email(
                reviewer_email=reviewer_email,
                reviewer_name=reviewer_name,
                author_name=author_name,
                doc_title=doc_title,
                doc_url=doc_url,
            )
        )

    background_tasks.add_task(_fire)
