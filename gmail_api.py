import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from creds_and_service import get_credentials, get_gmail_service as get_gmail_service_from_creds
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google_auth_httplib2
import httplib2
import os
import requests


def get_gmail_service(creds=None):
    """
    Create a new Gmail API service object for the current thread.
    
    Args:
        creds: Google credentials object (optional, will get from file if not provided)
    
    Returns:
        Gmail API service object
    """
    if creds is None:
        creds = get_credentials()
    return get_gmail_service_from_creds(creds)


def create_draft(service, to=None, subject=None, body=None, html_body=None, 
                 cc=None, bcc=None, attachments=None, thread_id=None, attachment_urls=None):
    """
    Create a Gmail draft with the specified content.
    
    Args:
        service: Gmail API service object
        to: Recipient email address(es) - string or list
        subject: Email subject
        body: Plain text body content
        html_body: HTML body content (optional, if not provided uses plain text)
        cc: CC recipient(s) - string or list
        bcc: BCC recipient(s) - string or list
        attachments: List of file paths to attach
        thread_id: Thread ID to add draft to (optional)
        attachment_urls: List of dicts with 'url' and optional 'filename' to attach from URLs
    Returns:
        Draft object with ID and message details
    """
    try:
        # Create the email message
        message = create_email_message(
            to=to, subject=subject, body=body, html_body=html_body,
            cc=cc, bcc=bcc, attachments=attachments, attachment_urls=attachment_urls
        )
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        # Create draft request
        draft_request = {
            'message': {
                'raw': raw_message
            }
        }
        # Add thread ID if specified
        if thread_id:
            draft_request['message']['threadId'] = thread_id
        # Create the draft
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        draft = service.users().drafts().create(
            userId='me',
            body=draft_request
        ).execute(http=http)
        print(f"✓ Draft created successfully with ID: {draft['id']}")
        return draft
    except HttpError as error:
        print(f"An error occurred creating draft: {error}")
        return None


def create_email_message(to=None, subject=None, body=None, html_body=None, 
                        cc=None, bcc=None, attachments=None, attachment_urls=None):
    """
    Create an email message object with the specified content.
    
    Args:
        to: Recipient email address(es) - string or list
        subject: Email subject
        body: Plain text body content
        html_body: HTML body content (optional)
        cc: CC recipient(s) - string or list
        bcc: BCC recipient(s) - string or list
        attachments: List of file paths to attach
        attachment_urls: List of dicts with 'url' and optional 'filename' to attach from URLs
    Returns:
        Email message object
    """
    # Create the message
    if html_body:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(body or '', 'plain'))
        message.attach(MIMEText(html_body, 'html'))
    else:
        message = MIMEMultipart()
        if body:
            message.attach(MIMEText(body, 'plain'))
    # Set headers
    if subject:
        message['Subject'] = subject
    # Handle recipients
    if to:
        if isinstance(to, list):
            message['To'] = ', '.join(to)
        else:
            message['To'] = to
    if cc:
        if isinstance(cc, list):
            message['Cc'] = ', '.join(cc)
        else:
            message['Cc'] = cc
    if bcc:
        if isinstance(bcc, list):
            message['Bcc'] = ', '.join(bcc)
        else:
            message['Bcc'] = bcc
    # Add local file attachments
    if attachments:
        for attachment_path in attachments:
            if os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}'
                )
                message.attach(part)
    # Add URL-based attachments
    if attachment_urls:
        for item in attachment_urls:
            url = item.get('url')
            filename = item.get('filename')
            if url:
                try:
                    resp = requests.get(url)
                    resp.raise_for_status()
                    data = resp.content
                    if not filename:
                        filename = url.split('/')[-1] or 'attachment'
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(data)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    message.attach(part)
                except Exception as e:
                    print(f"Failed to attach file from URL {url}: {e}")
    return message


def send_draft(service, draft_id):
    """
    Send a draft email.
    
    Args:
        service: Gmail API service object
        draft_id: ID of the draft to send
    
    Returns:
        Sent message object or None if failed
    """
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        sent_message = service.users().drafts().send(
            userId='me',
            body={'id': draft_id}
        ).execute(http=http)
        
        print(f"✓ Draft sent successfully. Message ID: {sent_message['id']}")
        return sent_message
        
    except HttpError as error:
        print(f"An error occurred sending draft: {error}")
        return None


def list_drafts(service, max_results=10):
    """
    List user's drafts.
    
    Args:
        service: Gmail API service object
        max_results: Maximum number of drafts to return
    
    Returns:
        List of draft objects
    """
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        drafts = service.users().drafts().list(
            userId='me',
            maxResults=max_results
        ).execute(http=http)
        
        return drafts.get('drafts', [])
        
    except HttpError as error:
        print(f"An error occurred listing drafts: {error}")
        return []


def get_draft(service, draft_id):
    """
    Get a specific draft by ID.
    
    Args:
        service: Gmail API service object
        draft_id: ID of the draft to retrieve
    
    Returns:
        Draft object or None if not found
    """
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        draft = service.users().drafts().get(
            userId='me',
            id=draft_id
        ).execute(http=http)
        
        return draft
        
    except HttpError as error:
        print(f"An error occurred getting draft: {error}")
        return None


def update_draft(service, draft_id, to=None, subject=None, body=None, 
                html_body=None, cc=None, bcc=None, attachments=None):
    """
    Update an existing draft.
    
    Args:
        service: Gmail API service object
        draft_id: ID of the draft to update
        to: Recipient email address(es) - string or list
        subject: Email subject
        body: Plain text body content
        html_body: HTML body content (optional)
        cc: CC recipient(s) - string or list
        bcc: BCC recipient(s) - string or list
        attachments: List of file paths to attach
    
    Returns:
        Updated draft object or None if failed
    """
    try:
        # Create the updated email message
        message = create_email_message(
            to=to, subject=subject, body=body, html_body=html_body,
            cc=cc, bcc=bcc, attachments=attachments
        )
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Update draft request
        draft_request = {
            'message': {
                'raw': raw_message
            }
        }
        
        # Update the draft
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        updated_draft = service.users().drafts().update(
            userId='me',
            id=draft_id,
            body=draft_request
        ).execute(http=http)
        
        print(f"✓ Draft updated successfully")
        return updated_draft
        
    except HttpError as error:
        print(f"An error occurred updating draft: {error}")
        return None


def delete_draft(service, draft_id):
    """
    Delete a draft.
    
    Args:
        service: Gmail API service object
        draft_id: ID of the draft to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        http = google_auth_httplib2.AuthorizedHttp(get_credentials(), http=httplib2.Http())
        service.users().drafts().delete(
            userId='me',
            id=draft_id
        ).execute(http=http)
        
        print(f"✓ Draft deleted successfully")
        return True
        
    except HttpError as error:
        print(f"An error occurred deleting draft: {error}")
        return False


def create_and_send_draft(service, to=None, subject=None, body=None, 
                         html_body=None, cc=None, bcc=None, attachments=None):
    """
    Create a draft and immediately send it.
    
    Args:
        service: Gmail API service object
        to: Recipient email address(es) - string or list
        subject: Email subject
        body: Plain text body content
        html_body: HTML body content (optional)
        cc: CC recipient(s) - string or list
        bcc: BCC recipient(s) - string or list
        attachments: List of file paths to attach
    
    Returns:
        Sent message object or None if failed
    """
    # First create the draft
    draft = create_draft(
        service=service, to=to, subject=subject, body=body,
        html_body=html_body, cc=cc, bcc=bcc, attachments=attachments
    )
    
    if draft:
        # Then send it
        return send_draft(service, draft['id'])
    
    return None


# Example usage functions
def example_create_simple_draft():
    """Example of creating a simple draft."""
    service = get_gmail_service()
    
    draft = create_draft(
        service=service,
        to='recipient@example.com',
        subject='Test Email Draft',
        body='This is a test email draft created via Gmail API.',
        html_body='<h1>Test Email Draft</h1><p>This is a test email draft created via Gmail API.</p>'
    )
    
    return draft


def example_create_draft_with_attachment():
    """Example of creating a draft with attachment from file and URL."""
    service = get_gmail_service()
    draft = create_draft(
        service=service,
        to=['recipient1@example.com', 'recipient2@example.com'],
        cc='cc@example.com',
        subject='Email with Attachment',
        body='Please find the attached file.',
        # attachments=['path/to/attachment.pdf'],
        attachment_urls=[{'url': 'https://tourism.gov.in/sites/default/files/2019-04/dummy-pdf_2.pdf', 'filename': 'file_from_url1.pdf'}]
    )
    return draft


if __name__ == "__main__":
    # Test the Gmail API functionality
    print("Testing Gmail API...")
    
    # Create a simple draft
    draft = example_create_draft_with_attachment()
    if draft:
        print(f"✓ Draft created with ID: {draft['id']}")
        
        # List drafts
        drafts = list_drafts(get_gmail_service())
        print(f"✓ Found {len(drafts)} drafts")
    else:
        print("✗ Failed to create draft")
