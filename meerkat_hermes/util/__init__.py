import uuid, boto3, urllib, datetime, time, json
from flask import current_app, Response
from boto3.dynamodb.conditions import Key, Attr

def send_email(destination, subject, message, html, sender):
    """
    Sends an email using Amazon SES. 
       
    Args:
        destination* - The email address to send to. ([Str])
        subject*     - The email subject. (Str)
        message*     - The message to be sent. (Str)
        html         - The html version of the message to be sent. (Str)
                       Defaults to the same as 'message'
        sender       - The sender's address. Must be an AWS SES verified email address.
                       Defaults to the config file SENDER value. 

    Returns:
        The Amazon SES response.
    """ 

    #Load the email client
    client = boto3.client('ses')

    if( not html ):
        html = message.replace( '\n', '<br />' )

    current_app.logger.warning('TESTING variable is currently: ' + str(current_app.config['TESTING']) )
    #If we are testing, use amazon mailbox simulators. 
    if current_app.config['TESTING']:
        destination = ['success@simulator.amazonses.com']

    response = client.send_email( 
        Source = sender,
        Destination = {
            'ToAddresses':destination
        },      
        Message = {
            'Subject':{
                'Data':subject,
                'Charset':current_app.config['CHARSET']
            },
            'Body':{
                'Text':{
                    'Data':message,
                    'Charset':current_app.config['CHARSET']
                },
                'Html':{
                    'Data':html,
                    'Charset':current_app.config['CHARSET']
                }
            }
        }    
    )

    response['SesMessageId'] = response.pop('MessageId')
    response['Destination'] = destination

    return response
    
def log_message( messageID, details ):
    """
    Logs that a message has been sent in the relavent dynamodb table. 
       
    Args:
        messageID*   - The unique message ID to be logged (Str)
                       Will fail if the messageID already exists.
        details*     - A dictionary containing any further details you wish to store.
                       Typically: destinations, message, time and medium. (Dict)

    Returns:
        The Amazon DynamoDB response.
    """ 
    db = boto3.resource('dynamodb')
    table = db.Table(current_app.config['LOG'])

    details['id'] = messageID
    response = table.put_item( Item=details )

    return response, 200

def send_sms( destination, message ):
    """
    Sends an sms message using Nexmo. 
       
    Args:
        destination* - The sms number to send to. (Str)
        message*     - The message to be sent. (Str)

    Returns:
        The Nexmo response.
    """ 
    params = {
        'api_key': current_app.config['NEXMO_PUBLIC_KEY'],
        'api_secret': current_app.config['NEXMO_PRIVATE_KEY'],
        'to': destination,
        'from': current_app.config['FROM'],
        'text': message
    }

    #If we are testing, don't actually send the message, we just return a dummy response.
    if current_app.config['TESTING']:
        response = { 
            "message-count": "1",
            "messages": [{
                    "message-id": "TEST-MESSAGE-ID",
                    "message-price": "0.03330000",
                    "network": "0000",
                    "remaining-balance": "3.58010000",
                    "status": "0",
                    "to": "01234567891"
            }]
        }

    #Otherwise send the message and return the response.
    else:
        url = 'https://rest.nexmo.com/sms/json?' + urllib.parse.urlencode(params)
        response = urllib.request.urlopen(url)
        response =  json.loads( response.read().decode('UTF-8')  )

    return response

def get_date():
    """
    Function to retreive a current timestamp.

       Returns:
           The current date and time in Y:M:DTH:M:S format.
    """
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y:%m:%dT%H:%M:%S')

def id_valid( messageID ):
    """
    Checks whether or not the given messageID has already been logged. 
    
    Returns:
        Boolean - True for a valid message ID, false for one that has already been logged.
    """
    table = boto3.resource('dynamodb').Table(current_app.config['LOG'])
    response = table.get_item( 
        Key={
            'id':messageID
        }
    )
    if 'Item' in response:
        return False 
    else:
        return True

def replace_keywords( message, subscriber ):

    for key in subscriber:
        placeholder = "<<"+key+">>"
        replace = str(subscriber[key])
        #If it's a list, e.g. topics, then it's a little more complicated.
        if isinstance(subscriber[key], list):
            replace = ""
            for i in range(len(subscriber[key])):
                replace += subscriber[key][i]
                if i < len(subscriber[key])-2: replace += ', '
                elif i == len(subscriber[key])-2: replace += ' and '
        message = message.replace( placeholder, replace )
    return message
    
def create_subscriptions( subscriber_id, topics ):

    db = boto3.resource('dynamodb')
    table = db.Table(current_app.config['SUBSCRIPTIONS'])

    with table.batch_writer() as batch:
        for topic_id in topics:
            batch.put_item(
                Item={
                    'subscriptionID': uuid.uuid4().hex,
                    'topicID': topic_id,
                    'subscriberID': subscriber_id
                }
            )

def delete_subscriber(subscriber_id):
    """
    Delete a subscriber from the database. At the moment, if a user wishes to change
    information, they need to delete themselves and then re-add themselves with the
    new information.

    Args:
         subscriber_id
    Returns:
         The amazon dynamodb response.
    """

    db = boto3.resource('dynamodb')
    subscribers = db.Table(current_app.config['SUBSCRIBERS'])
    subscriptions = db.Table(current_app.config['SUBSCRIPTIONS'])

    subscribers_response = subscribers.delete_item( 
        Key={
            'id':subscriber_id
        }
    )

    #dynamoDB doesn't currently support deletions by secondary indexes (it may appear in the future). 
    #Deleteing by subscriber index is therefore a two hop process.
    #(1) Query for the primary key values i.e.topicID (2) Using topicID's, batch delete the records.
    query_response = subscriptions.query(
        IndexName='subscriberID-index',
        KeyConditionExpression=Key('subscriberID').eq(subscriber_id)
    )

    with subscriptions.batch_writer() as batch:
        for record in query_response['Items']:
            batch.delete_item(
                Key={ 
                   'subscriptionID': record['subscriptionID']
                }
            )       

    
    status = 200   
    response = "<html><body><H2>You have been successfully unsubscribed.</H2></body</html>"
    mimetype = 'text/html'

    if not subscribers_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        if not query_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            status = 500
            response = "{'message':'500 Internal Server Error: Unable to complete deletion.'}"
            mimetype = 'application/json'

    return Response( response, 
                     status=status,
                     mimetype=mimetype ) 
