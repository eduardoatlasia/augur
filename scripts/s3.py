"""
Script to sync local files to S3 and between S3 buckets.

# Go to flu build.
cd augur/builds/flu

# Download flu H3N2 data into auspice directory.
python ../../scripts/s3.py pull nextstrain-dev-data \
    --prefixes flu_h3n2 --to auspice

# Upload flu H3N2 data to S3 dev bucket.
python ../../scripts/s3.py push nextstrain-dev-data \
    auspice/flu_h3n2_*

# Upload the same data to the production bucket.
python ../../scripts/s3.py push nextstrain-data \
    auspice/flu_h3n2_*

# Download all production data into the working directory.
python ../../scripts/s3.py pull nextstrain-data
"""
import argparse
import boto3
import logging
import logging.config
import os


def push(bucket_name, files, cloudfront_id=None, dryrun=False):
    """Push the given files to the given S3 bucket and optionally invalidate the
    cache for a given CloudFront id.

    Args:
        bucket_name: S3 bucket to pull from
        files: a list of local files to upload to the given bucket
        cloudfront_id: a CloudFront id to use for a cache invalidation
        dryrun: boolean indicating whether files should be downloaded or not
    """
    # Setup logging.
    logger = logging.getLogger(__name__)

    # Create a distinct list of files to push.
    files = list(set(files))

    # Confirm that all given file paths are proper files.
    for file_name in files:
        assert os.path.isfile(file_name), "The requested input '%s' is not a proper file" % file_name

    # Connect to S3.
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucket_name)

    # Upload local files, stripping directory names from the given file paths
    # for the S3 keys.
    logger.info("Uploading %i files to bucket '%s'" % (len(files), bucket_name))
    for file_name in files:
        s3_key = os.path.split(file_name)[-1]
        logger.debug("Uploading '%s' as '%s'" % (file_name, s3_key))

        if not dryrun:
            bucket.upload_file(file_name, s3_key)

    if cloudfront_id is not None:
        logger.debug("Invalidating cache for CloudFront id '%s'" % cloudfront_id)


def pull(bucket_name, prefixes=None, local_dir=None, dryrun=False):
    """Pull files from the given S3 bucket. Optionally, only pull files that match
    the given list of filename prefixes.

    Args:
        bucket_name: S3 bucket to pull from
        prefixes: a list of key prefixes to filter objects in the bucket by
        local_dir: a local directory to download files into
        dryrun: boolean indicating whether files should be downloaded or not
    """
    # Setup logging.
    logger = logging.getLogger(__name__)

    # Confirm that the given local directory is a real directory.
    if local_dir is not None:
        assert os.path.isdir(local_dir), "The requested output directory '%s' is not a proper directory." % local_dir

    # Connect to S3.
    s3 = boto3.resource("s3")

    # Get a list of all objects in the requested bucket.
    bucket = s3.Bucket(bucket_name)

    # Get objects that match the given list of prefixes. If no prefixes are
    # given, get all objects.
    if prefixes is not None:
        object_keys = []
        for prefix in prefixes:
            keys = [obj.key for obj in bucket.objects.filter(Prefix=prefix)]
            object_keys.extend(keys)

        object_keys = sorted(set(object_keys))
    else:
        object_keys = sorted([obj.key for obj in bucket.objects.all()])

    # Download objects.
    logger.info("Downloading %i files from bucket '%s'" % (len(object_keys), bucket_name))
    for key in object_keys:
        # Download into a local directory if requested.
        if local_dir is not None:
            local_key = os.path.join(local_dir, key)
        else:
            local_key = key

        logger.debug("Downloading '%s' as '%s'" % (key, local_key))
        if not dryrun:
            bucket.download_file(key, local_key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_const", dest="loglevel", const=logging.INFO, help="Enable verbose logging")
    parser.add_argument("--debug", "-d", action="store_const", dest="loglevel", const=logging.DEBUG, help="Enable debugging logging")
    parser.add_argument("--dryrun", "-n", action="store_true", help="Perform a dryrun without uploading or downloading any files")

    subparsers = parser.add_subparsers(dest="command_name")

    parser_push = subparsers.add_parser("push")
    parser_push.add_argument("--cloudfront_id", "-c", help="CloudFront id to use to create a cache invalidation")
    parser_push.add_argument("bucket", help="S3 bucket to push files to")
    parser_push.add_argument("files", nargs="+", help="One or more sets of files to push to the given bucket")
    parser_push.set_defaults(func=push)

    parser_pull = subparsers.add_parser("pull")
    parser_pull.add_argument("bucket", help="S3 bucket to pull files from")
    parser_pull.add_argument("--prefixes", "-p", nargs="+", help="One or more file prefixes to match in the given bucket")
    parser_pull.add_argument("--local_dir", "--to", "-t", help="Local directory to download files into")
    parser_pull.set_defaults(func=pull)

    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    try:
        if args.command_name == "push":
            args.func(args.bucket, args.files, args.cloudfront_id, args.dryrun)
        elif args.command_name == "pull":
            args.func(args.bucket, args.prefixes, args.local_dir, args.dryrun)
    except AssertionError, e:
        parser.error(e.message)
