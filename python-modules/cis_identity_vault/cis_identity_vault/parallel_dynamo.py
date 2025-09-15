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
    users = response.get("Items", [])
    last_evaluated_key = response.get("LastEvaluatedKey")

    while last_evaluated_key is not None:
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = dynamodb_client.scan(**scan_kwargs)
        users.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")

    logger.debug("Running thread_id: {}".format(thread_id))
    return result_queue.put(dict(users=users, nextPage=last_evaluated_key, segment=thread_id))


def scan(
    dynamodb_client, table_name, filter_expression, expression_attr, projection_expression, exclusive_start_key=None
):
    logger.debug("Creating new threads and queue.")
    result_queue = queue.Queue()

    # The worker pool size should be equal to the max_segments. Ideally we want one segment per worker.
    pool_size = 128
    max_segments = 128

    users = []
    last_evaluated_key = None
    threads = []

    for thread_id in range(0, pool_size):
        # What are we passing to each threaded function.

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
        users_additional = result.get("users")
        users.extend(users_additional)
        if result.get("segment") == max_segments - 1:
            logger.debug("This is the last segment.")
            last_evaluated_key = result.get("nextPage")
            logger.debug("Last evaluated key in page was: {}".format(last_evaluated_key))
        result_queue.task_done()

    logger.debug("Results queue is empty.")
    return dict(users=users, nextPage=last_evaluated_key)
