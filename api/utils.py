import os
from os.path import join
import json
import uuid
from django.conf import settings
import boto3
from minid_client import minid_client_api
from bdbag import bdbag_api


def create_bag_archive(metadata, bag_algorithms=('md5', 'sha256'),
                       **bag_metadata):
    bag_name = join(settings.BAG_STAGING_DIR, str(uuid.uuid4()))
    metadata_file = join(settings.BAG_STAGING_DIR, str(uuid.uuid4()))
    with open(metadata_file, 'w') as f:
        f.write(json.dumps(metadata))

    os.mkdir(bag_name)
    bdbag_api.make_bag(bag_name,
                       algs=bag_algorithms,
                       metadata=dict(bag_metadata),
                       remote_file_manifest=metadata_file,
                       )
    bdbag_api.archive_bag(bag_name, settings.BAG_ARCHIVE_FORMAT)

    archive_name = '{}.{}'.format(bag_name, settings.BAG_ARCHIVE_FORMAT)
    bdbag_api.revert_bag(bag_name)
    os.remove(metadata_file)
    return archive_name


def _register_minid(filename, aws_bucket_filename,
                    minid_email, minid_title, minid_test):
    checksum = minid_client_api.compute_checksum(filename)
    return minid_client_api.\
        register_entity(
                        settings.MINID_SERVER,
                        checksum,
                        minid_email,
                        settings.MINID_SERVICE_TOKEN,
                        ["https://s3.amazonaws.com/%s/%s" % (
                             settings.AWS_BUCKET_NAME,
                             aws_bucket_filename
                        )],
                        minid_title,
                        minid_test
                        )


def create_minid(filename, aws_bucket_filename, minid_user,
                 minid_email, minid_title, minid_test):
    minid = _register_minid(filename, aws_bucket_filename,
                            minid_email, minid_title, minid_test)
    if not minid \
            and not minid_client_api.get_user(
                settings.MINID_SERVER,
                minid_email).get('user'):
        minid_client_api.register_user(settings.MINID_SERVER,
                                       minid_email,
                                       minid_user,
                                       '',  # ORCID is not currently used
                                       settings.MINID_SERVICE_TOKEN)
        minid = _register_minid(filename, aws_bucket_filename,
                                minid_email, minid_title, minid_test)
        if not minid:
            raise Exception("Failed to register minid "
                            "and user autoregistration failed")
    return minid


def upload_to_s3(filename, key):
    s3 = boto3.resource('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    with open(filename, 'rb') as data:
        s3.Bucket(settings.AWS_BUCKET_NAME).upload_fileobj(
            data,
            key,
            ExtraArgs={'ACL': 'public-read'}
        )
