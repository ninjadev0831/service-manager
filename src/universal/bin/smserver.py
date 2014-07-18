#!/usr/bin/env python

import signal
import sys
import argparse
import traceback

from bottle import route, run, request, response
from server import smserverlogic

from smcontext import SmApplication
from smutil import pretty_print_list

parser = argparse.ArgumentParser(description='Service Manager Server - Start, Stop and View services')
parser.add_argument('-c', '--conf', type=str, help='Specify the folder holding service configuration files')
parser.add_argument('-n', '--nosource', action='store_true', help='Prevent services from starting if the request asks to start them from source (return an error 400)')
parser.add_argument('-F', '--feature', action='append', help='Enable a given feature for all services started')
parser.add_argument('-o', '--offline', action='store_true', help='Offline mode: uses existing binaries instead of looking for an updated version online')
args = parser.parse_args()

feature_string = pretty_print_list("All requests to this server will have feature$s $list enabled.", args.feature)
if feature_string:
    print feature_string

if args.nosource:
    print "No-source is specified, 'SOURCE' will not be accepted as a 'runFrom' parameter"

SERVER = smserverlogic.SmServer(SmApplication(args.conf, args.feature))


@route('/ping', method='GET')
def ping():
    response.status = 200
    return "pong"


@route('/start', method='POST')
def start():
    try:
        print SERVER

        try:
            json_body = request.json
        except Exception:
            raise BadRequestException("Invalid JSON")

        print str(json_body)

        return smserverlogic.SmStartRequest(SERVER, json_body, args.nosource, args.offline).process_request()
    except BadRequestException as e:
        return smserverlogic.SmResponse.bad_request(e.message)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return smserverlogic.SmResponse.error_500(e.message)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


@route('/stop', method='POST')
def stop():
    try:

        try:
            json_body = request.json
        except Exception:
            raise BadRequestException("Invalid JSON")

        print str(request.json)

        return smserverlogic.SmStopRequest(SERVER, json_body, args.offline).process_request()
    except BadRequestException as e:
        return smserverlogic.SmResponse.bad_request(e.message)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return smserverlogic.SmResponse.error_500(e.message)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


@route('/version_variable', method='GET')
def get_version_variable():
    try:
        return smserverlogic.SmVersionRequest(SERVER).process_request()
    except BadRequestException as e:
        return smserverlogic.SmResponse.bad_request(e.message)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return smserverlogic.SmResponse.error_500(e.message)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


class BadRequestException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


#DO NOT REMOVE UNUSED FRAME PARAM - it's need for signal handler
def signal_handler(sig, frame):
    try:
        print "Signal received: %s" % sig
        smserverlogic.SmShutdownRequest(SERVER).process_request()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

run(host=smserverlogic.RUN_ON_HOST, port=smserverlogic.RUN_ON_PORT)
