try:
    from .creds_and_service import get_drive_service, get_credentials
except ImportError:
    from creds_and_service import get_drive_service, get_credentials
import io


def create_folder(service, folder_name, parent_id=None, completion_callback=None):
    """
    Create a folder in Google Drive.
    
    Args:
        service: Google Drive service object
        folder_name: Name for the folder in Drive
        parent_id: ID of parent folder (None for default drive root)
        completion_callback: Function to call when creation completes (error, response)
    
    Returns:
        Folder ID of the created folder
    """
    print(f'Creating folder {folder_name} with parentId: {parent_id}')
    
    # Folder metadata
    folder_metadata = {
        'name': folder_name,
        'driveId': "0AF8AbuEbPrCOUk9PVA",
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    if parent_id:
        folder_metadata['parents'] = [parent_id]
    
    try:
        # Create the folder
        response = service.files().create(
            body=folder_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        # Folder created successfully
        folder_id = response.get('id')
        print(f'Created folder {folder_name} in Drive Successfully. Folder ID: {folder_id}')
        
        # Call completion callback
        if completion_callback:
            completion_callback(None, response)
        
        return folder_id
        
    except Exception as err:
        print(f"Folder creation error: {err}")
        if completion_callback:
            completion_callback(err, None)
        raise


def upload_file(service, file_path_or_stream, filename, mime_type, parent_id=None, progress_callback=None, completion_callback=None):
    """
    Upload a file to Google Drive with progress tracking.
    
    Args:
        service: Google Drive service object
        file_path_or_stream: Local file path or file-like object (stream)
        filename: Name for the file in Drive
        mime_type: MIME type of the file
        parent_id: ID of parent folder (None for default drive root)
        progress_callback: Function to call with progress updates (uploaded_bytes, total_bytes)
        completion_callback: Function to call when upload completes (error, response)
    
    Returns:
        File ID of the uploaded file
    """
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    import os

    # Determine if we're working with a file path or stream
    if isinstance(file_path_or_stream, str):
        if not os.path.exists(file_path_or_stream):
            raise FileNotFoundError(f"File not found: {file_path_or_stream}")
        total_size = os.path.getsize(file_path_or_stream)
        is_file_path = True
    else:
        # It's a stream - try to get size
        current_pos = file_path_or_stream.tell()
        file_path_or_stream.seek(0, 2)  # Seek to end
        total_size = file_path_or_stream.tell()
        file_path_or_stream.seek(current_pos)  # Restore position
        is_file_path = False
    
    # Emit initial progress
    if progress_callback:
        progress_callback(0, total_size, filename)
    
    print(f'Uploading file {filename} with parentId: {parent_id}')
    
    # File metadata
    file_metadata = {
        'name': filename,
        'driveId': "0AF8AbuEbPrCOUk9PVA",
        'mimeType': mime_type
    }
    
    if parent_id:
        file_metadata['parents'] = [parent_id]
    else:
        file_metadata['parents'] = ["0AF8AbuEbPrCOUk9PVA"]
    
    try:
        # Create media upload object
        if is_file_path:
            media = MediaFileUpload(
                file_path_or_stream, 
                mimetype=mime_type,
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
        else:
            media = MediaIoBaseUpload(
                file_path_or_stream,
                mimetype=mime_type,
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
        
        # Create the upload request
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        )
        
        # Progress tracking variables
        uploaded_bytes = 0
        
        # Execute resumable upload with progress tracking
        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    uploaded_bytes = int(status.resumable_progress)
                    if progress_callback:
                        progress_callback(uploaded_bytes, total_size, filename)
                    
                    print(f"Upload progress: {uploaded_bytes}/{total_size} bytes ({uploaded_bytes/total_size*100:.1f}%)")
                
            except Exception as chunk_error:
                print(f"Upload chunk error: {chunk_error}")
                if completion_callback:
                    completion_callback(chunk_error, None)
                raise
        
        # Upload completed successfully
        file_id = response.get('id')
        print(f'Uploaded {filename} to Drive Successfully. File ID: {file_id}')
        
        # Final progress update
        if progress_callback:
            progress_callback(total_size, total_size, filename)
        
        # Call completion callback
        if completion_callback:
            completion_callback(None, response)
        
        return file_id
        
    except Exception as err:
        print(f"Upload error: {err}")
        if completion_callback:
            completion_callback(err, None)
        raise

    # Example progress callback
def progress_callback(uploaded, total, filename):
    percentage = (uploaded / total) * 100 if total > 0 else 0
    print(f"📤 {filename}: {uploaded:,}/{total:,} bytes ({percentage:.1f}%)")

# Example completion callback
def completion_callback(error, response):
    if error:
        print(f"❌ Upload failed: {error}")
    else:
        print(f"✅ Upload completed successfully!")




if __name__ == "__main__":
    # Get credentials
    creds = get_credentials(token='token.json', client_secret='client_secrets.json')
    
    # Create Drive service
    service = get_drive_service(creds)
    
    print("Google Drive service initialized.")

    # available mime types (not exhaustive, but only the ones I've tested):
        # text/plain
        # text/markdown
        # application/vnd.google-apps.folder
    
    # Example folder creation using the new create_folder function
    folder_id = create_folder(
        service,
        "folder-test",
        completion_callback=completion_callback
    )

    # Example file upload using the new upload_file function
    file_bytes = b"Hello, world!"
    file_stream = io.BytesIO(file_bytes)
    upload_file(
        service,
        file_stream,
        "test.md",
        "text/markdown",
        parent_id=folder_id,
        progress_callback=progress_callback,
        completion_callback=completion_callback
    )

    
 