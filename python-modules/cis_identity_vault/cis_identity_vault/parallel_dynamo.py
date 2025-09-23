"""Centralize logic for parallelism of scanning ops."""
import queue
import threading

from logging import getLogger


logger = getLogger(__name__)


def get_segment(
    result_queue,
    thread_id,
    dynamodb_client,
    table_name,
    filter_expression,
    expression_attr,
    projection_expression,
    exclusive_start_key,
    total_segments,
):
    scan_kwargs = dict(
        TableName=table_name, TotalSegments=total_segments, Segment=thread_id, FilterExpression=filter_expression
    )

    if projection_expression:
        scan_kwargs["ProjectionExpression"] = projection_expression
    else:
        scan_kwargs["ProjectionExpression"] = "id, primary_email, user_uuid, active"

    if exclusive_start_key:
        scan_kwargs["ExclusiveStartKey"] = exclusive_start_key

    if expression_attr:
        scan_kwargs["ExpressionAttributeValues"] = expression_attr

    logger.debug("Running parallel scan with kwargs: {}".format(scan_kwargs))
    response = dynamodb_client.scan(**scan_kwargs)
    # Return a dictionary of users, since sets can only contain hashable types
    # (and lists and dicts are not).
    users = {
        user["id"]["S"]: user
        for user in response.get("Items", [])
    }
    last_evaluated_key = response.get("LastEvaluatedKey")

    logger.debug("Finished thread_id: {}, with nextPage: {}".format(thread_id, last_evaluated_key))
    return result_queue.put(dict(users=users, nextPage=last_evaluated_key, segment=thread_id))


def scan(
    dynamodb_client, table_name, filter_expression, expression_attr, projection_expression, exclusive_start_keys=None
):
    logger.debug("Creating new threads and queue.")
    result_queue = queue.Queue()

    # We use one worker per segment.
    max_segments = 48

    users = dict()
    last_evaluated_keys = [None] * max_segments
    threads = []
    start = False

    # If this is the first request, then we'll receive a None from our caller.
    if exclusive_start_keys is None:
        start = True
        exclusive_start_keys = [None] * max_segments

    # When we're continuing, we signal that a segment has no more work to
    # complete if it's ESK is `None`. If _all_ of the segments have that, then
    # we're at the end of our result set.
    if not start and all(map(lambda esk: esk is None, exclusive_start_keys)):
        return dict(users=[], nextPage=None)

    for thread_id in range(0, max_segments):
        # What are we passing to each threaded function.
        try:
            exclusive_start_key = exclusive_start_keys[thread_id]
        except IndexError:
            logger.critical("Someone may be DOSing us or not doing pagination properly.")
            raise

        # If we started already and read a `None`, then this is a signal that
        # the segment has no more records.
        if not start and exclusive_start_key is None:
            logger.debug(f"skipping thread {thread_id}")
            continue

        thread_args = (
            result_queue,
            thread_id,
            dynamodb_client,
            table_name,
            filter_expression,
            expression_attr,
            projection_expression,
            exclusive_start_key,
            max_segments,
        )

        logger.debug(
            "thread starting scan",
            extra={
                "thread_id": thread_id,
                "table_name": table_name,
                "filter_expression": filter_expression,
                "expression_attr": expression_attr,
                "projection_expression": projection_expression,
                "exclusive_start_key": exclusive_start_key,
                "max_segments": max_segments,
            }
        )
        threads.append(threading.Thread(target=get_segment, args=thread_args))
        threads[-1].start()

    logger.debug("Waiting for threads to terminate...")
    for t in threads:
        t.join()

    logger.debug("Retrieving results from the queue...")

    while not result_queue.empty():
        logger.debug("Results queue is not empty.")
        result = result_queue.get()
        users.update(result.get("users", {}))
        segment = result.get("segment")
        last_evaluated_keys[segment] = result.get("nextPage")
        result_queue.task_done()

    logger.debug("Results queue is empty.")
    return dict(users=users.values(), nextPage=last_evaluated_keys)
