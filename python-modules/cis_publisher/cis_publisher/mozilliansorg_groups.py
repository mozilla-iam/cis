import logging

logger = logging.getLogger(__name__)


class MozilliansorgGroupsPublisher:

    def publish(self, event):
        """
        Noop

        @event: raw event from SQS
        """
        logger.info("Skipping event from CISv1")
