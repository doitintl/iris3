import logging
import typing

from google.cloud import pubsub_v1

from pluginbase import Plugin
from util import gcp_utils


class Pubsub(Plugin):
    @classmethod
    def googleapiclient_discovery(cls) -> typing.Tuple[str, str]:
        return ('pubsub', 'v1')

    def api_name(self):
        return "pubsub.googleapis.com"

    def method_names(self):
        # Actually "google.pubsub.v1.Subscriber.CreateSubscription" but a substring is allowed
        return ["CreateSubscription"]

    def do_label(self, project_id):
        # TODO Add paging
        request = self._google_client.projects().subscriptions().list(
            project='projects/' + project_id)
        response = request.execute()
        logging.debug(response)
        for subscription in response['subscriptions']:
            logging.info('one subscription %s', subscription)
            self.label_one(subscription, project_id)

        if self.counter > 0:
            self.do_batch()

        return 'OK', 200

    def label_one(self, gcp_object, project_id):

        org_labels = {}
        try:
            org_labels = gcp_object['labels']
        except KeyError:
            pass

        labels = dict(
            [('labelFingerprint', gcp_object.get('labelFingerprint', ''))])
        labels['labels'] = self._gen_labels(gcp_object)
        for k, v in org_labels.items():
            labels['labels'][k] = v

        name = gcp_object['name']

        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(gcp_utils.project_id(), iris_subscription())

        subscription = pubsub_v1.types.Subscription(
            name=subscription_path, topic=iris_topic(), labels={"a": "b"}
        )

        update_mask = {"paths": {"labels"}}

        # Wrap the subscriber in a 'with' block to automatically call close() to
        # close the underlying gRPC channel when done.
        with subscriber:
            result = subscriber.update_subscription(
                request={"subscription": subscription, "update_mask": update_mask}
            )
            print('result')

        print(f"Subscription updated: {subscription_path}")
        self.counter += 1
        if self.counter == 1000:
            self.do_batch()
        return 'OK', 200

    def get_gcp_object(self, data):
        # TODO remove excess logs
        logging.info('get_gcp_object ' + str(data))
        proj = data['resource']['labels']['project_id']
        instId = data['protoPayload']['request']['instanceId']
        logging.info('proj ' + proj + ' instId ' + instId)
        try:
            ERRORnstance = self._get_subscription(proj, instId)
            return instance
        except Exception as e:
            logging.error(e)
            return None

    def _get_subscription(self, project_id, name):
        pass

    def _get_name(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        return gcp_utils.get_name(gcp_object)

    def _get_region(self, gcp_object):
        """Method dynamically called in _gen_labels, so don't change name"""
        try:
            region = gcp_object['region']
            region = region.lower()
            return region
        except KeyError as e:
            logging.error(e)
            return None
    # TODO more info for pubsub subscription?
