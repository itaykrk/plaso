#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Tests for the Google Analytics cookies."""

import unittest

from plaso.formatters import ganalytics as _  # pylint: disable=unused-import
from plaso.lib import eventdata
from plaso.lib import timelib
from plaso.parsers.cookie_plugins import ganalytics
from plaso.parsers.sqlite_plugins import chrome_cookies
from plaso.parsers.sqlite_plugins import firefox_cookies

from tests.parsers.sqlite_plugins import test_lib as sqlite_plugins_test_lib


class GoogleAnalyticsPluginTest(sqlite_plugins_test_lib.SQLitePluginTestCase):
  """Tests for the Google Analytics plugin."""

  def _GetAnalyticsCookieEvents(self, storage_writer):
    """Retrieves the analytics cookie events.

    Returns:
      A list of analytics cookie event objects (instances of
      GoogleAnalyticsEvent).
    """
    cookies = []
    for event_object in storage_writer.events:
      if isinstance(event_object, ganalytics.GoogleAnalyticsEvent):
        cookies.append(event_object)
    return cookies

  def testParsingFirefox29CookieDatabase(self):
    """Tests the Process function on a Firefox 29 cookie database file."""
    plugin_object = firefox_cookies.FirefoxCookiePlugin()
    storage_writer = self._ParseDatabaseFileWithPlugin(
        [u'firefox_cookies.sqlite'], plugin_object)
    event_objects = self._GetAnalyticsCookieEvents(storage_writer)

    self.assertEqual(len(event_objects), 25)

    event_object = event_objects[14]

    self.assertEqual(
        event_object.utmcct,
        u'/frettir/erlent/2013/10/30/maelt_med_kerfisbundnum_hydingum/')
    expected_timestamp = timelib.Timestamp.CopyFromString(
        u'2013-10-30 21:56:06')
    self.assertEqual(event_object.timestamp, expected_timestamp)
    self.assertEqual(event_object.url, u'http://ads.aha.is/')
    self.assertEqual(event_object.utmcsr, u'mbl.is')

    expected_msg = (
        u'http://ads.aha.is/ (__utmz) Sessions: 1 Domain Hash: 137167072 '
        u'Sources: 1 Last source used to access: mbl.is Ad campaign '
        u'information: (referral) Last type of visit: referral Path to '
        u'the page of referring link: /frettir/erlent/2013/10/30/'
        u'maelt_med_kerfisbundnum_hydingum/')

    self._TestGetMessageStrings(
        event_object, expected_msg, u'http://ads.aha.is/ (__utmz)')

  def testParsingChromeCookieDatabase(self):
    """Test the process function on a Chrome cookie database."""
    plugin_object = chrome_cookies.ChromeCookiePlugin()
    storage_writer = self._ParseDatabaseFileWithPlugin(
        [u'cookies.db'], plugin_object)
    event_objects = self._GetAnalyticsCookieEvents(storage_writer)

    # The cookie database contains 560 entries in total. Out of them
    # there are 75 events created by the Google Analytics plugin.
    self.assertEqual(len(event_objects), 75)
    # Check few "random" events to verify.

    # Check an UTMZ Google Analytics event.
    event_object = event_objects[39]
    self.assertEqual(event_object.utmctr, u'enders game')
    self.assertEqual(event_object.domain_hash, u'68898382')
    self.assertEqual(event_object.sessions, 1)

    expected_msg = (
        u'http://imdb.com/ (__utmz) Sessions: 1 Domain Hash: 68898382 '
        u'Sources: 1 Last source used to access: google Ad campaign '
        u'information: (organic) Last type of visit: organic Keywords '
        u'used to find site: enders game')
    self._TestGetMessageStrings(
        event_object, expected_msg, u'http://imdb.com/ (__utmz)')

    # Check the UTMA Google Analytics event.
    event_object = event_objects[41]
    self.assertEqual(event_object.timestamp_desc, u'Analytics Previous Time')
    self.assertEqual(event_object.cookie_name, u'__utma')
    self.assertEqual(event_object.visitor_id, u'1827102436')
    self.assertEqual(event_object.sessions, 2)

    expected_timestamp = timelib.Timestamp.CopyFromString(
        u'2012-03-22 01:55:29')
    self.assertEqual(event_object.timestamp, expected_timestamp)

    expected_msg = (
        u'http://assets.tumblr.com/ (__utma) '
        u'Sessions: 2 '
        u'Domain Hash: 151488169 '
        u'Visitor ID: 1827102436')
    self._TestGetMessageStrings(
        event_object, expected_msg, u'http://assets.tumblr.com/ (__utma)')

    # Check the UTMB Google Analytics event.
    event_object = event_objects[34]
    self.assertEqual(
        event_object.timestamp_desc, eventdata.EventTimestamp.LAST_VISITED_TIME)
    self.assertEqual(event_object.cookie_name, u'__utmb')
    self.assertEqual(event_object.domain_hash, u'154523900')
    self.assertEqual(event_object.pages_viewed, 1)

    expected_timestamp = timelib.Timestamp.CopyFromString(
        u'2012-03-22 01:48:30')
    self.assertEqual(event_object.timestamp, expected_timestamp)

    expected_msg = (
        u'http://upressonline.com/ (__utmb) Pages Viewed: 1 Domain Hash: '
        u'154523900')
    self._TestGetMessageStrings(
        event_object, expected_msg, u'http://upressonline.com/ (__utmb)')


if __name__ == '__main__':
  unittest.main()
