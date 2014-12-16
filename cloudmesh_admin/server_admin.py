from __future__ import print_function

import subprocess
import json
import hostlist
from cloudmesh_install import config_file
from cloudmesh.config.ConfigDict import ConfigDict
from cloudmesh_common.logger import LOGGER
from cloudmesh_install.util import banner
import sys
import os
import sh
import time
from cloudmesh_install.util import path_expand
from cloudmesh.config.cm_config import cm_config_server
from pprint import pprint

# ----------------------------------------------------------------------
# SETTING UP A LOGGER
# ----------------------------------------------------------------------

log = LOGGER(__file__)


def isyes(value):
    check = str(value).lower()
    if check in ['true', 'false', 'y', 'n', 'yes', 'no']:
        return check in ['true', 'y', 'yes']
    else:
        print ("parameter not in", ['true', 'false', 'y', 'n', 'yes', 'no'])
        print ("found", value, check)
        sys.exit()


class cloudmesh_server(object):

    def _ps(self):
        return sh.ps("-ax", _tty_out=False)

    def __init__(self):

        self.server_env = {
            "name": "server"
        }

        self.rabbit_env = {
            'rabbitmq_server': "sudo rabbitmq-server",
            'rabbitmqctl': "sudo rabbitmqctl",
            'detached': ""
        }
        try:
            import cloudmesh
        except Exception, e:
            print ("ERROR: could not find package\n\n   cloudmesh\n")
            print ("please run first\n")
            print ("     ./install cloudmesh\n")
            banner()
            print (e)
            banner()
        # import cloudmesh_web
        # self.server_env['location'] = os.path.dirname(cloudmesh_web.__file__)
        self.server_env['location'] = "./cloudmesh_web"
        celery_config = ConfigDict(
            filename=config_file("/cloudmesh_celery.yaml"),
            kind="worker")
        self.workers = celery_config.get("cloudmesh.workers")

        for worker in self.workers:
            self.workers[worker]["hostlist"] = hostlist.expand_hostlist(
                "{0}[1-{1}]".format(self.workers[worker]["id"],
                                    self.workers[worker]["count"]))
        print(json.dumps(self.workers, indent=4))

        self.celery_cmd = sh.which("celery")
        # print ("CCCC", self.celery_cmd)
        # sys.exit()

    def info(self):
        #
        # getting the basic mongo info
        #
        banner("mongo info")
        d = {}
        d['mongo'] = self._info_mongo()
        print ("Mongo pid", d['mongo']['pid'])
        print ("Mongo port", d['mongo']['port'])

        d['celery'] = self._info_celery()
        pprint(d)

    def start(self):
        """starts in dir webgui the program server.py and displays a browser on the
            given port and link
        """
        self._start_web_server()
        self._start_mongo()
        # banner("KILL THE SERVER", debug=debug)
        # kill(debug=debug)

        # mongo.start()
        # execute_command("START MONGO",
        #            "fab mongo.start",
        #             debug)

        # queue.start()
        # execute_command("START RABITMQ",
        #        "fab queue.start", debug)

        # queue.flower_server()
        # execute_command("START FLOWER",
        #        "fab queue.flower_server",
        #        debug)

        pass

    def stop(self):
        self._stop_web_server()
        self._stop_mongo()

    def status(self):
        pass

    # ######################################################################
    # WEB SERVER
    # ######################################################################

    def _stop_web_server(self):
        # stop web server
        banner("stop the web server")
        try:
            result = sh.fgrep(
                sh.fgrep(self._ps(),
                         "python {name}.py".format(**self.server_env)),
                "-v", "fgrep"
            ).split("\n")[:-1]
            print (result)

            for line in result:
                if line is not '':
                    pid = line.split(" ")[0]
                    print (line)
                    print ("PID", pid)
                    print ("KILL")
                    try:
                        sh.kill("-9", str(pid))
                    except Exception, e:
                        print ("ERROR")
                        print (e)
        except Exception, e:
            print ("INFO: cloudmesh web server not running")

    def _start_web_server(self):
        # from cloudmesh_web import server as cloudmesh_web_server_start
        banner("start the web server")
        os.system("cd cloudmesh_web; python server.py &")
        time.sleep(4)

    # ######################################################################
    # CELERY SERVER
    # ######################################################################

    def _info_celery(self):
        d = {}

        try:
            lines = sh.grep(
                sh.grep(self._ps(), "celery"), "worker").split("\n")[:-1]
            for line in lines:
                (pid, command) = line.lstrip().split(" ", 1)
                d[pid] = line
        except:
            pass
        return d

    def _stop_celery(self):
        processes = self._info_celery()
        print (processes.keys())
        for pid in processes:
            try:
                sh.kill("-9", str(pid))
            except:
                print (pid, " process already deleted")

    def _celery_command(self, command, app, workers, queue, concurrency=None):
        """execute the celery command on the application and workers
        specified"""
        worker_str = " ".join(workers)
        parameter_string = "celery multi {0} {1} -A {2} -l info -Q {3}".format(
            command, worker_str, app, queue)
        # directories for log and pid file
        celery_dir = path_expand("~/.cloudmesh/celery")
        sh.mkdir("-p", celery_dir)
        parameter_string += " --pidfile=\"{0}/%n.pid\" ".format(celery_dir)
        parameter_string += " --logfile=\"{0}/%n.log\" ".format(celery_dir)
        if concurrency is not None:
            parameter_string += " --concurrency={0}".format(concurrency)
        print(parameter_string)
        proc = subprocess.Popen(parameter_string,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                )
        stdout_value, stderr_value = proc.communicate()

        # print (stdout_value)
        # print (stderr_value)

    def _start_celery(self):
        # mq.start()

        for worker in self.workers:
            print (worker)
            print (json.dumps(self.workers[worker]))
            concurrency = None
            if "concurrency" in self.workers[worker]:
                concurrency = self.workers[worker]["concurrency"]
            self._celery_command(
                "start",
                self.workers[worker]["app"],
                self.workers[worker]["hostlist"],
                self.workers[worker]["queue"],
                concurrency=concurrency)

    # ######################################################################
    # MONGO SERVER
    # ######################################################################

    def _info_mongo(self):
        config = cm_config_server().get("cloudmesh.server.mongo")
        path = path_expand(config["path"])
        port = config["port"]
        # print (config)
        # print(port, path)

        d = {
            'pid': None,
            'port': None,
            'path': None,
            'command': None
        }

        try:
            lines = sh.grep(
                sh.grep(self._ps(), "mongod"), "log").split("\n")[:-1]
            if lines != ['']:
                (pid) = lines[0].lstrip().split(" ")[0]
                d = {'pid': pid,
                     'port': port,
                     'path': path,
                     'command': lines}
        except:
            pass
        return d

    def _start_mongo(self):
        """
        start the mongod service in the location as specified in
        cloudmesh_server.yaml
        """
        banner("Starting mongod")
        config = cm_config_server().get("cloudmesh.server.mongo")
        path = path_expand(config["path"])
        port = config["port"]

        banner("creating dir")
        if not os.path.exists(path):
            print ("Creating mongodb directory in {0}".format(path))
            sh.mkdir("-p", path)
        banner("check")
        try:
            lines = sh.grep(sh.grep(sh.ps("-ax"), "mongod"), "log")
            banner("LINES")
            print (lines)
            if lines != ['']:
                pid = lines[0].split(" ")[0]
                print ("NO ACTION: mongo already running in pid "
                       "{0} for port {1}".format(pid, port))
            return

        except Exception, e:
            print ("INFO: No cloudmesh mongo server running")

        banner("LLLLLL")
        print (lines)

        print ("ACTION: Starting mongod")
        print
        print ("NOTE: the preparation of mongo may take a few minutes")
        print ("      please do not interrupt this program.")
        print
        print ("      Please be patient!")
        print

        sh.mongod("--auth",
                  "--bind_ip", "127.0.0.1"
                  "--fork",
                  "--dbpath", path,
                  "--logpath", "{0}/mongodb.log".format(path),
                  "--port",  port,
                  _bg=True)

    def _stop_mongo(self):
        """starts in dir webgui the program server.py and displays a
            browser on the given port and link """
        try:
            sh.killall("-15", "mongod")
        except:
            print ("INFO: cloudmesh mongo server not running")


'''
        queue.start()
        # execute_command("START RABITMQ",
        #        "fab queue.start", debug)

        queue.flower_server()
        # execute_command("START FLOWER",
        #        "fab queue.flower_server",
        #        debug)

    def _queue_start(view=None):
        """start the celery server

        :param: if view is set to any value start also rabit and attach
                to it so we can see the log
        """
        # pprint (fabric.state.output)
        with settings(warn_only=True):
            stop()
            time.sleep(2)
            mq.start()
            time.sleep(2)

            for worker in workers:
                concurrency = None
                if "concurrency" in workers[worker]:
                    concurrency = workers[worker]["concurrency"]
                # print worker, ":   ", str(workers[worker])
                celery_command("start", workers[worker]["app"],
                               workers[worker]["hostlist"], workers[
                                   worker]["queue"],
                               concurrency=concurrency)

        if view is None:
            time.sleep(2)
            print
            # local("celery worker --app={0} -l info".format(app))
            # local("celery worker -l info".format(app))

    def _mq_start(self):
        set_rabbitmq_env()
        if detached is None:
            rabbit_env['detached'] = "-detached"
        # log.info (rabbit_env)
        local("{rabbitmq_server} {detached}".format(**rabbit_env))

    def _mq_stop():
        """stop the rabbit mq server"""
        local("{rabbitmqctl} stop".format(**rabbit_env))

    def _set_rabbitmq_env():

        location = path_expand("~/.cloudmesh/rabbitm")

        if sys.platform == "darwin":
            mkdir("-p", location)
            rabbit_env["RABBITMQ_MNESIA_BASE"] = location
            rabbit_env["RABBITMQ_LOG_BASE"] = location
            os.environ["RABBITMQ_MNESIA_BASE"] = location
            os.environ["RABBITMQ_LOG_BASE"] = location
            rabbit_env["rabbitmq_server"] = \
                "/usr/local/opt/rabbitmq/sbin/rabbitmq-server"
            rabbit_env["rabbitmqctl"] = \
                "/usr/local/opt/rabbitmq/sbin/rabbitmqctl"
        elif sys.platform == "linux2":
            mkdir("-p", location)
            rabbit_env["RABBITMQ_MNESIA_BASE"] = location
            rabbit_env["RABBITMQ_LOG_BASE"] = location
            os.environ["RABBITMQ_MNESIA_BASE"] = location
            os.environ["RABBITMQ_LOG_BASE"] = location
            rabbit_env["rabbitmq_server"] = "/usr/sbin/rabbitmq-server"
            rabbit_env["rabbitmqctl"] = "/usr/sbin/rabbitmqctl"
        else:
            print("WARNING: cloudmesh rabbitmq user install not supported, "
                  "using system install")
'''

if __name__ == '__main__':
    server = cloudmesh_server()
    server.info()

    # server.start()
    # server.stop()
    # server._start_mongo()
    # server.stop()

    server._stop_celery()
    server._start_celery()