from mock import *

import unittest
from hamcrest import *

from smstatus import dostatus
from service.smservice import SmServiceStatus
from service.smjvmservice import SmJvmService
from smcontext import ServiceManagerException
import time


class JvmServiceMock(SmJvmService):

    def __init__(self, context, service_name):
        SmJvmService.__init__(self, context, service_name, "")

    def post_stop(self):
        pass

    def get_port_argument(self):
        pass

    def get_running_healthcheck_port(self, process):
        pass

    def get_details_url(self):
        pass


class ProcessMock(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class TestSmJvmServiceStatus(unittest.TestCase):

    def setUp(self):
        self.context = MagicMock()
        self.context.exception = lambda message: ServiceManagerException(message)
        self.context.service_type = lambda x: ''

    def process(self, cmdline):
        return ProcessMock(cmdline=lambda: cmdline, pid=1, ppid=lambda: 10, memory_info=lambda: [10], create_time=lambda: time.time())

    def test_matches_running_service(self):
        mock = JvmServiceMock(self.context, "TEST")
        status = mock.status([self.process(["service.manager.serviceName=TEST"])])
        assert_that(status, is_not(empty()))
        assert_that(status, contains(has_property("service_name", "TEST")))

    def test_fails_to_match_other_service(self):
        mock = JvmServiceMock(self.context, "TEST")
        status = mock.status([self.process(["service.manager.serviceName=NOTEST"])])
        assert_that(status, is_(empty()))

    def test_fails_to_match_service_with_prefix_of_this_service(self):
        mock = JvmServiceMock(self.context, "TEST")
        status = mock.status([self.process(["service.manager.serviceName=TEST-STUBS"])])
        assert_that(status, is_(empty()))

    def test_fails_to_match_service_with_cmdline_including_space(self):
        mock = JvmServiceMock(self.context, "TEST")
        status = mock.status([self.process(["-Dhttp.port=9051 -Dservice.manager.serviceName=TEST -Dservice.manager.runFrom=SOURCE"])])
        assert_that(status, is_not(empty()))

    def test_return_pass_when_healthcheck_passes(self):
        mock = JvmServiceMock(self.context, "TEST")
        mock.run_healthcheck = lambda x: True
        status = mock.status([self.process(["service.manager.serviceName=TEST"])])
        assert_that(status, contains(has_property("healthcheck", "PASS")))

    def test_return_boot_when_healthcheck_is_booting(self):
        mock = JvmServiceMock(self.context, "TEST")
        mock.run_healthcheck = lambda x: False
        status = mock.status([self.process(["service.manager.serviceName=TEST"])])
        assert_that(status, contains(has_property("healthcheck", "BOOT")))