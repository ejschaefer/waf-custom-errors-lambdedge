import json
import os
import boto3
import logging


logger = logging.getLogger()
logger.setLevel("INFO")

client = None
ddb_client = None
template_content = None

bucket_name = None #'catchall-playground-multi-use-bucket-us-east-1'
ddb_table_name = "LambdaEdgeParameters"
object_key = 'errors/404.html'

local_file = '/tmp/404.html'
cache_mode = "memory"

def get_bucket_name():
    global client
    if client is None:
        client = boto3.client('dynamodb', region_name='us-east-1')
    res = client.get_item(
        TableName=ddb_table_name,
        Key={
            'PK': {'S': 'ErrorPageBucketName'}
        }
    )
    return res['Item']['Value']['S']

def cache_s3_to_tmp():
    global bucket_name
    if bucket_name is None:       
        bucket_name = get_bucket_name()
    with open(local_file, 'wb') as file:
        client.download_fileobj(bucket_name, object_key, file)

def cache_s3_to_memory():
    global template_content, bucket_name
    if bucket_name is None:       
        bucket_name = get_bucket_name()
    res = client.get_object(Bucket=bucket_name, Key=object_key)
    template_content = res['Body'].read().decode('utf-8')
    return template_content
    
def get_error_page():
    if cache_mode == "disk":
        logger.info(f'Loading template from disk')
        if not os.path.exists(local_file):
            logger.info(f'Loading template from S3 (disk)')
            cache_s3_to_tmp()
        with open(local_file, 'r') as file:
            content = file.read()
        
    else:
        logger.info(f'Loading template from memory')
        if template_content is None:
            logger.info(f'Loading template from S3 (memory)')
            content = cache_s3_to_memory()
        else:
            content = template_content

    return content


def build_response(content, status_code, status_message):
    response = {
        'status': status_code,
        'statusDescription': status_message,
        'headers': {
            'cache-control': [
                {
                    'key': 'Cache-Control',
                    'value': 'max-age=100'
                }
            ],
            "content-type": [
                {
                    'key': 'Content-Type',
                    'value': 'text/html'
                }
            ]
        },
        'body': content
    }

    return response


def lambda_handler(event, context):
    global client

    logger.debug(f'Received event: {json.dumps(event)}')
    
    if client is None:
        client = boto3.client('s3', region_name='us-east-1')
    
    request = event['Records'][0]['cf']['request']
    if request and request['uri'] == '/errors/404.html':
        request_id = event['Records'][0]['cf']['config'].get('requestId', 'REQUEST_ID_NOT_FOUND')
        logger.debug(f'Processing Error Page Request Id {request_id}')
        
        template = get_error_page()
        body_content = template.replace('__CF_REQUEST_ID__', request_id)
        response = build_response(body_content, 200, 'OK')

        return response

    return request