"""Offline compatibility check with the pinned real SDK; never connects to MAX."""
import inspect
from pymax import WebClient, Message
from collector import envelope, millis
from test_collector import SOURCE, NOW

params = inspect.signature(WebClient.fetch_history).parameters
assert {'chat_id', 'backward', 'from_time', 'interactive'} <= set(params)
post = Message(id=1, time=millis(NOW)-1000, type='CHANNEL', text='Тест')
result = envelope(post, SOURCE, millis(NOW))
assert result['channel_id'] == SOURCE['chat_id']
assert result['channelBinding'] == 'verified_history_request'
assert result['requiresReview'] is False
print('Pinned MAX SDK: pagination parameters and real Message envelope OK (offline)')
