"""SNS notification publisher adapter."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.domain.ports import NotificationPublisherPort

logger = logging.getLogger(__name__)


class SnsNotificationPublisherAdapter(NotificationPublisherPort):
    def __init__(self, sns_client: Any) -> None:
        self._sns = sns_client
        self._topic_arns: dict[str, str] = {}

    async def _get_topic_arn(self, topic_name: str) -> str | None:
        if topic_name in self._topic_arns:
            return self._topic_arns[topic_name]
        try:
            response = await asyncio.to_thread(self._sns.list_topics)
            for t in response.get("Topics", []):
                arn = t["TopicArn"]
                if arn.endswith(f":{topic_name}"):
                    self._topic_arns[topic_name] = arn
                    return arn
        except Exception as exc:
            logger.warning("Could not list SNS topics: %s", exc)
        return None

    async def publish_notification(self, topic_name: str, message: dict[str, Any]) -> None:
        arn = await self._get_topic_arn(topic_name)
        if not arn:
            logger.info("SNS topic '%s' not yet found; skipping SNS publish.", topic_name)
            return

        await asyncio.to_thread(
            self._sns.publish,
            TopicArn=arn,
            Message=json.dumps(message, default=str),
            Subject=f"Data Governance Diagnostic - {message.get('requestId')}",
        )
