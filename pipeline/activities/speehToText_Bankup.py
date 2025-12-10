# import azure.durable_functions as df
# import requests
# import logging
# import time
# from datetime import datetime, timedelta
# from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
# from configuration import Configuration

# name = "speechToText"
# bp = df.Blueprint()

# def wait_for_transcription(transcription_url, headers, check_interval=10, timeout_minutes=60):
#     """Poll the transcription status until it's complete or timeout is reached"""
#     start_time = time.time()
#     timeout_seconds = timeout_minutes * 60

#     while True:
#         status_response = requests.get(transcription_url, headers=headers)
#         logging.info(f"Polling STT URL: {transcription_url} - Response code: {status_response.status_code}")
#         status = status_response.json()
#         current_status = status.get('status', 'Unknown')
#         logging.info(f"STT Status: {current_status}")

#         if current_status == 'Succeeded':
#             logging.info("Transcription completed successfully!")
#             return status
#         elif current_status == 'Failed':
#             logging.error(f"Transcription failed! Details: {status}")
#             return status
#         elif time.time() - start_time > timeout_seconds:
#             logging.error("Transcription polling timed out.")
#             return {"status": "Failed", "error": "Polling timed out"}
#         else:
#             logging.info(f"Waiting {check_interval} seconds before checking again...")
#             time.sleep(check_interval)

# def generate_blob_sas_url(blob_name: str, container_name: str = "bronze", expiry_minutes: int = 60):
#     """Generate a SAS URL for the given blob using Managed Identity"""
#     config = Configuration()
#     account_name = "st4zlbpuh65bt3w"  # Hardcoded storage account

#     logging.info(f"Generating SAS URL for blob: {blob_name} in container: {container_name}")

#     blob_service_client = BlobServiceClient(
#         account_url=f"https://{account_name}.blob.core.windows.net",
#         credential=config.credential
#     )

#     key_start = datetime.utcnow()
#     key_expiry = key_start + timedelta(minutes=expiry_minutes)
#     logging.info(f"Requesting user delegation key from {key_start} to {key_expiry}")
    
#     user_delegation_key = blob_service_client.get_user_delegation_key(key_start, key_expiry)
#     logging.info(f"User delegation key obtained successfully")

#     sas_token = generate_blob_sas(
#         account_name=account_name,
#         container_name=container_name,
#         blob_name=blob_name,
#         user_delegation_key=user_delegation_key,
#         permission=BlobSasPermissions(read=True),
#         expiry=key_expiry
#     )

#     sas_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
#     logging.info(f"Generated SAS URL: {sas_url}")
#     return sas_url

# @bp.function_name(name)
# @bp.activity_trigger(input_name="blob_input")
# def run(blob_input: dict):
#     try:
#         blob_name = blob_input.get("name")
#         logging.info(f"Received blob input: {blob_input}")

#         if not blob_name:
#             raise ValueError("Blob name missing in input")

#         # 1️⃣ Generate SAS URL for the blob
#         blob_sas_url = generate_blob_sas_url(blob_name)

#         # Test access to the blob before sending to STT
#         logging.info(f"Testing access to blob SAS URL: {blob_sas_url}")
#         test_resp = requests.head(blob_sas_url)
#         logging.info(f"HEAD request response: {test_resp.status_code}, headers: {test_resp.headers}")

#         # 2️⃣ Get token for Cognitive Services
#         config = Configuration()
#         token = config.credential.get_token("https://cognitiveservices.azure.com/.default").token
#         logging.info(f"Obtained Cognitive Services token: {token[:20]}... (truncated)")

#         endpoint = config.get_value("AIMULTISERVICES_ENDPOINT")  # e.g., "https://<your-resource>.cognitiveservices.azure.com"
#         api_version = "2025-10-15"
#         url = f"{endpoint}/speechtotext/transcriptions:submit?api-version={api_version}"
#         logging.info(f"STT submission URL: {url}")

#         headers = {
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {token}"
#         }

#         # 3️⃣ Submit transcription request
#         payload = {
#             "displayName": f"Transcription_{blob_name}",
#             "locale": "en-US",
#             "contentUrls": [blob_sas_url],
#             "properties": {
#                 "wordLevelTimestampsEnabled": False,
#                 "displayFormWordLevelTimestampsEnabled": False,
#                 "punctuationMode": "DictatedAndAutomatic",
#                 "profanityFilterMode": "Masked",
#                 "timeToLiveHours": 48
#             }
#         }

#         logging.info(f"Submitting transcription request payload: {payload}")
#         response = requests.post(url, json=payload, headers=headers)
#         logging.info(f"STT submission response: {response.status_code}, body: {response.text}")
#         response.raise_for_status()
#         transcription_url = response.json()['self']

#         # 4️⃣ Wait for transcription to complete
#         final_status = wait_for_transcription(transcription_url, headers)

#         if final_status['status'] != 'Succeeded':
#             logging.error(f"Error during transcription: {final_status}")
#             return "Error during speech-to-text processing."

#         # 5️⃣ Retrieve transcription result
#         files_url = final_status['links']['files']
#         logging.info(f"Fetching transcription files from: {files_url}")
#         files_response = requests.get(files_url, headers=headers)
#         logging.info(f"Files response code: {files_response.status_code}, body: {files_response.text}")
#         files_response.raise_for_status()

#         phrases = []
#         for file in files_response.json().get('values', []):
#             content_url = file['links']['contentUrl']
#             logging.info(f"Fetching content URL: {content_url}")
#             content_response = requests.get(content_url).json()
#             phrases.extend([p['display'] for p in content_response.get('combinedRecognizedPhrases', [])])

#         full_text = " ".join(phrases)
#         logging.info(f"Transcribed text: {full_text}")

#         return full_text

#     except Exception as e:
#         logging.error(f"Error during speech-to-text processing: {e}", exc_info=True)
#         return "Error during speech-to-text processing."
