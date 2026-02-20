import os
import json
import time
import datetime
import boto3

ROUTE_GET_MY_IP = "my-ip"
ROUTE_PERSISTED_IP = "persisted-ip"
DYNAMO_DB_TABLE = os.environ["TABLE_NAME"]
TEST_MACHINE_ID = "test"
TEST_IP_ADDRESS = "test-invoke-source-ip"
IP_STORE_TTL = 1296000  # 15 days in seconds
LOCAL_RUN = False if "LOCAL_RUN" not in os.environ else os.environ["LOCAL_RUN"] == "TRUE"
CORS_ORIGINS = ('http://traffic.enroute.im', 'http://talk.enroute.im')


def success_response(body=None, allow_cors=False):
    if body is None:
        body = {}
    headers = {
        "content-type": "application/json"
    }
    if allow_cors:
        headers['Access-Control-Allow-Origin'] = ', '.join(CORS_ORIGINS)
        headers['Access-Control-Allow-Methods'] = "OPTIONS, GET"
        headers['Access-Control-Allow-Headers'] = "Accept, Content-Type"
    return {
        "statusCode": 200,
        "body": json.dumps(body),
        "headers": headers
    }


def get_source_ip(event):
    if event and "requestContext" in event and "identity" in event["requestContext"] \
            and "sourceIp" in event["requestContext"]["identity"]:
        return event["requestContext"]["identity"]["sourceIp"]
    else:
        return "bad event format"


def init_dynamodb_table():
    if LOCAL_RUN:
        return boto3.resource('dynamodb', endpoint_url="http://localhost:8000").Table(DYNAMO_DB_TABLE)
    else:
        return boto3.resource("dynamodb").Table(DYNAMO_DB_TABLE)


def save_machine_ip(machine_id: str, machine_ip: str, ttl: int = 0) -> bool:
    if machine_id == TEST_MACHINE_ID or machine_ip == TEST_IP_ADDRESS:
        return False
    else:
        table = init_dynamodb_table()
        table.put_item(
            Item={
                'id': machine_id,
                'ip': machine_ip,
                'ttl': 0 if not ttl else int(time.time()) + ttl,
                'time': datetime.datetime.now().isoformat()
            }
        )
        return True


def get_machine_ip(machine_id: str) -> tuple[str, str]:
    table = init_dynamodb_table()
    response = table.get_item(
        Key={
            'id': machine_id
        }
    )
    saved_time = "unknown"
    if "Item" in response and "time" in response['Item']:
        saved_time = response['Item']['time']
    return (response['Item']['ip'], saved_time) if 'Item' in response else ("not found", saved_time)


def lambda_handler(event, context):
    """Ip Memo main handler

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    if event and event["httpMethod"] == 'OPTIONS' and ROUTE_GET_MY_IP in event['path']:
        return success_response(allow_cors=True)

    if event and event["httpMethod"] == 'GET' and ROUTE_GET_MY_IP in event['path']:
        return success_response({"ip": get_source_ip(event)}, True)

    if event and event["httpMethod"] == 'GET' and ROUTE_PERSISTED_IP in event['path']:
        machine_id = event["pathParameters"]["machine_id"]
        ip_data = get_machine_ip(machine_id)
        return success_response({"machine_id": machine_id,
                                 "machine_ip": ip_data[0],
                                 "saved_on": ip_data[1]})

    if event and event["httpMethod"] == 'POST' and ROUTE_PERSISTED_IP in event['path']:
        machine_id = event["pathParameters"]["machine_id"]
        machine_ip = get_source_ip(event)
        return success_response({"machine_id": machine_id,
                                 "machine_ip": machine_ip,
                                 "saved": save_machine_ip(machine_id, machine_ip, IP_STORE_TTL)})

    return success_response({
        "message": "hello world"
    })
