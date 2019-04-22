from chalice import Chalice
from contextlib import closing
import os
import uuid
from tempfile import gettempdir

import boto3
from labels_graphical import * #why reinvent wheels when i have a perfectly good one in the shop
import csv

app = Chalice(app_name='SayLabels1')
# turn on debugging messages
app.debug = True

BUCKET_NAME = 'lambda-assignment-bucket'


def get_awsLogin():

    lineC = 0
    secretKey = ''
    accessKey = ''
    with open('credentials-2.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for col in csv_reader:
            if(lineC == 1):
                accessKey += col[2]
                secretKey += col[3]
            lineC += 1

    loginCred = (accessKey,secretKey )

    return loginCred


#global variable that contains the login credentials
loginCred = get_awsLogin()


def upload_to_s3(filename, bucket, folder=None, public=False):
    """
    Uploads the file to the specified bucket
    :param bucket: the name of the bucket to upload to
    :param filename: the name of the file
    :param folder: optional folder to upload to
    :param public: whether to make it publicly readable
    """
    app.log.debug('Creating S3 client')
    s3 = boto3.client('s3',
                      aws_access_key_id=loginCred[0],
                      aws_secret_access_key=loginCred[1],
                      region_name='us-east-2')

    app.log.debug('Uploading to S3')
    local_filename = os.path.join(gettempdir(), filename)
    s3_name = ''
    if folder is not None:
        s3_name = '{}/{}'.format(folder, filename)
        app.log.debug('Uploading {} to {} in bucket {}'.format(local_filename, s3_name, bucket))
        s3.upload_file(local_filename,
                       bucket,
                       s3_name)
    else:
        s3_name = '{}'.format(filename)
        app.log.debug('Uploading {} to {} in bucket {}'.format(local_filename, s3_name, bucket))
        s3.upload_file(local_filename,
                       bucket,
                       s3_name)

    if public:
        app.log.debug('Changing ACL of {} in bucket {}'.format(s3_name, bucket))
        s3.put_object_acl(ACL='public-read',
                          Bucket=bucket,
                          Key=s3_name)


def text_to_speech(text, voice, bucket, folder=None):
    """
    Uses AWS Polly to convert the given text to speech
    :param text: the text to convert
    :param voice: the voice to use
    :param bucket: the name of the S3 bucket to upload the mp3 file to.
    :param folder: the (optional) folder within the S3 bucket in which to upload the mp3 file.
    :return: the url of where to access the converted file.
    """
    # code taken from/based on
    # https://aws.amazon.com/blogs/ai/build-your-own-text-to-speech-applications-with-amazon-polly/,
    # last access 10/29/2017
    rest = text

    # Because single invocation of the polly synthesize_speech api can
    # transform text with about 1,500 characters, we are dividing the
    # post into blocks of approximately 1,000 characters.
    app.log.debug('Chunking text')
    text_blocks = []
    while len(rest) > 1100:
        begin = 0
        end = rest.find(".", 1000)

        if end == -1:
            end = rest.find(" ", 1000)

        text_block = rest[begin:end]
        rest = rest[end:]
        text_blocks.append(text_block)
    text_blocks.append(rest)
    # app.log.debug('Done chunking text {}'.format(text_blocks))

    # For each block, invoke Polly API, which will transform text into audio
    app.log.debug('Creating polly client')

    polly = boto3.client('polly',
                         aws_access_key_id=loginCred[0],
                         aws_secret_access_key=loginCred[1],
                         region_name='us-east-2')
    filename = '{}.mp3'.format(uuid.uuid4())
    for text_block in text_blocks:
        response = polly.synthesize_speech(
            OutputFormat='mp3',
            Text=text_block,
            VoiceId=voice
        )

        # Save the audio stream returned by Amazon Polly on Lambda's temp
        # directory. If there are multiple text blocks, the audio stream
        # will be combined into a single file.
        if "AudioStream" in response:
            with closing(response["AudioStream"]) as stream:
                output = os.path.join(gettempdir(), filename)
                with open(output, "ab") as file:
                    file.write(stream.read())

    # Play the audio using the platform's default player
    # import sys
    # import subprocess
    # if sys.platform == "win32":
    #     os.startfile(output)
    # else:
    #     # the following works on Mac and Linux. (Darwin = mac, xdg-open = linux).
    #     opener = "open" if sys.platform == "darwin" else "xdg-open"
    #     subprocess.call([opener, output])

    upload_to_s3(filename, bucket, folder, True)
    result = None
    if folder is not None:
        result = 'https://{bucket}.s3.amazonaws.com/{folder}/{filename}'.format(bucket=bucket, folder=folder,
                                                                                filename=filename)
    else:
        #result = 'https://s3.amazonaws.com/{bucket}/{filename}'.format(bucket=bucket,filename=filename)

        #defitniely wasnt right before this url does return the mp3 however
        result = 'http://{bucket}.s3.amazonaws.com/{filename}'.format(bucket=bucket,filename=filename)

    app.log.debug('Returning URL {}'.format(result))
    return result






# for the route below, the path should be
# your (and your partner's) initials
# for example, my route would be '/pv/{voice}'
@app.route('/zb/{voice}', content_types=['image/png', 'image/jpeg', 'image/jpg'], methods=['POST'], cors=True)
def sayLabels1(voice):
    app.log.debug('gets image')

    # gets the images bytes from the file upload
    imgbytes = app.current_request.raw_body

    # rest of your code here
    app.log.debug('getting labels')

    #gets labels
    labellist = get_labels(imgbytes, 77) #modified get labels function slighty to not worry about getting the image bytes

    isHotdog = False

    if "Hot Dog" in labellist: isHotdog = True

    app.log.debug('join labels')

    #turns list into a single string
    labelliststr = ' , '.join(labellist)

    # calls the get labels function from labels graphical assignment, no need to revintent the wheel
    #{voice: "Nicole", labels: "Human, People, Person, Team", url: "s3://url to the mp3 file"}
    if imgbytes is None or voice is None:
        return {'Error': 'image and/or voice not set'}

    if(isHotdog):
        return {
            'voice': voice,
            'labels': labelliststr,
            'url': text_to_speech("this is a hotdog" , voice, BUCKET_NAME, True)
        }
    else:
        return {
            'voice': voice,
            'labels': labelliststr,
            'url': text_to_speech( "this is not a hotdog", voice, BUCKET_NAME, True)
        }



