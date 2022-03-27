import os
import datetime
import io
import json
import re 

from gtts import gTTS


from google.cloud.documentai_v1beta3.types import document
from google.cloud import vision

from fastapi import FastAPI, File, UploadFile

from google.cloud import storage

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()

templates = Jinja2Templates(directory="src")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "restate_keys.json"

client = vision.ImageAnnotatorClient()


origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000"
    
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root(request:Request):
    result = "Go to /docs for using api"
    return templates.TemplateResponse("index.html",{"request" : request ,"result": result})

# @app.get("/")
# def read_root():
#     return ["Go to /docs for using api"]


@app.post("/uploadfile")
async def create_upload_file(file: UploadFile = File(...)):
    #  The ID of your GCS bucket
    bucket_name = "test-fastapi"
    # The path to your file to upload
    source_filename = file.file
    # The ID of your GCS object
    destination_blobname = str(file.filename)

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blobname)

    blob.upload_from_file(source_filename,content_type='application/pdf')

    print(
        "File {} uploaded to {}.".format(
            source_filename, destination_blobname
        )
    )
    gcs_source_uri = 'gs://test-fastapi/{}'.format(destination_blobname)
    gcs_destination_uri = 'gs://test-fastapi/result'
    url = await async_detect_document(gcs_source_uri,gcs_destination_uri = 'gs://test-fastapi/result')

    return {"url"}



def async_detect_document(gcs_source_uri,gcs_destination_uri):
    """OCR with PDF/TIFF as source files on GCS"""
    

    # Supported mime_types are: 'application/pdf' and 'image/tiff'
    mime_type = 'application/pdf'

    # How many pages should be grouped into each json output file.
    batch_size = 20

    client = vision.ImageAnnotatorClient()

    feature = vision.Feature(
        type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)

    gcs_source = vision.GcsSource(uri=gcs_source_uri)
    input_config = vision.InputConfig(
        gcs_source=gcs_source, mime_type=mime_type)

    gcs_destination = vision.GcsDestination(uri=gcs_destination_uri)
    output_config = vision.OutputConfig(
        gcs_destination=gcs_destination, batch_size=batch_size)

    async_request = vision.AsyncAnnotateFileRequest(
        features=[feature], input_config=input_config,
        output_config=output_config)

    operation = client.async_batch_annotate_files(
        requests=[async_request])

    print('Waiting for the operation to finish.')
    operation.result(timeout=420)

    # Once the request has completed and the output has been
    # written to GCS, we can list all the output files.
    storage_client = storage.Client()

    match = re.match(r'gs://([^/]+)/(.+)', gcs_destination_uri)
    bucket_name = match.group(1)
    prefix = match.group(2)

    bucket = storage_client.get_bucket(bucket_name)

    # List objects with the given prefix.
    blob_list = list(bucket.list_blobs(prefix=prefix))
    print('Output files:')
    for blob in blob_list:
        print(blob.name)

    # Process the first output file from GCS.
    # Since we specified batch_size=2, the first response contains
    # the first two pages of the input file.
    output = blob_list[0]


    json_string = output.download_as_string()
    response = json.loads(json_string)
    print(type(response))

    # Here we print the full text from all the pages.
    # The response contains more information:
    # annotation/pages/blocks/paragraphs/words/symbols
    # including confidence scores and bounding boxes
    
    page_responses = response['responses']
    all_text = ''
    for page in page_responses:
        all_text += page['fullTextAnnotation']['text'] + '\n'
        
    # print(all_text)
    print(len(all_text))
    
    # def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    bucket_name = "test-fastapi"
    # The path to your file to upload
    ob = gTTS(text=all_text, lang='en', slow=False)
    fname= "newname.mp3"
    
    ob.save(fname)
    source = os.path.abspath(fname)
    print(type)
    source_file_name = source
    # The ID of your GCS object
    destination_blob_name = fname

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(
        "File {} uploaded to {}.".format(
            source_file_name, destination_blob_name
        )
    )
    url = blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=datetime.timedelta(minutes=15),
        # Allow GET requests using this URL.
        method="GET",
    )
    print(url)
    
    
    return url