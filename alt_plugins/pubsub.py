import logging

from google.cloud import pubsub_v1

from pluginbase import Plugin
# CREDENTIALS = app_engine.Credentials(scopes=SCOPES)
from util import gcp_utils


# from utils.pubsub_utils import logs_topic, logs_subscription


# SCOPES = ['https://www.googleapis.com/auth/pubsub']


class PubSub(Plugin):

    def __init__(self):
        Plugin.__init__(self)

    def register_signals(self):
        logging.debug("Cloud PubSub class created and registering signals")

    def api_name(self):
        return "pubsub.googleapis.com"

    def method_names(self):
        # Actually "google.pubsub.v1.Subscriber.CreateSubscription" but a subscript is allowed
        return ["CreateSubscription"]

    def do_label(self, project_id):
        logging.info('pubsub dotag')
        # TODO Add paging
        request = self.pubsub.projects().subscriptions().list(
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
        self.counter = self.counter + 1
        if self.counter == 1000:
            self.do_batch()
        return 'OK', 200

    def get_gcp_object(self, data):
        logging.info("get_gcp_object " + str(data))
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


'''
    def get_gcp_object(self, data):
        try:
            instance = self._get_topic(
                data['resource']['labels']['project_id'],
                data['protoPayload']['request']['instanceId'])
            return instance
        except Exception as e:
            logging.error(e)
            return None

    def __get_name(self, gcp_object):
        try:
            name = gcp_object['name']
            name = name.replace(".", "_").lower()[:62]
        except KeyError as e:
            logging.error(e)
            return None
        logging.info('pubsub name '+name)
        return name

    #TODO This and other __get_region are probably unused
    def __get_region(self, gcp_object):
        try:
            region = gcp_object['region']
            region = region.lower()
        except KeyError as e:
            logging.error(e)
            return None
        return region
'''
