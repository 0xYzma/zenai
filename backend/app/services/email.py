"""
Email Service for sending password reset links and notifications.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_settings
from app.core.logger import logger

def send_reset_email(to_email: str, token: str):
    settings = get_settings()
    reset_link = f"{settings.app_host}/reset-password?token={token}"
    
    # Simple fallback for MVP when SMTP is not configured
    if not hasattr(settings, 'smtp_server') or not settings.smtp_server:
        logger.logger.info(f"[MOCK EMAIL] Password reset link for {to_email}: {reset_link}")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = settings.smtp_sender
        msg['To'] = to_email
        msg['Subject'] = "ZenAI Password Reset"

        body = f"Click the link to reset your ZenAI password:\n\n{reset_link}\n\nIf you did not request this, please ignore this email."
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(settings.smtp_server, getattr(settings, 'smtp_port', 587))
        server.starttls()
        
        if hasattr(settings, 'smtp_username') and hasattr(settings, 'smtp_password'):
            server.login(settings.smtp_username, settings.smtp_password)
            
        server.send_message(msg)
        server.quit()
        logger.logger.info(f"Password reset email sent to {to_email}")
    except Exception as e:
        logger.logger.error(f"Failed to send reset email to {to_email}: {e}")
