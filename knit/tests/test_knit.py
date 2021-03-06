import os
import time
import pytest
import socket

from knit import Knit
from knit.exceptions import HDFSConfigException, KnitException


def check_docker():
    """check if inside docker container"""
    return os.path.exists('/.dockerenv')

inside_docker = check_docker


def wait_for_status(k, status, timeout=30):
    cur_status = k.runtime_status()
    while cur_status != status and timeout > 0:
        print("Current status is {0}, waiting for {1}".format(cur_status, status))

        time.sleep(2)
        timeout -= 2
        cur_status = k.runtime_status()
        
    return timeout > 0
        

def wait_for_containers(k, running_containers, timeout=30):
    cur_running_containers = k.status()['app']['runningContainers']
    while cur_running_containers != running_containers and timeout > 0:
        print("Current number of containers is {0}, waiting for {1}".format(cur_running_containers, running_containers))

        time.sleep(2)
        timeout -= 2
        cur_running_containers = k.status()['app']['runningContainers']
        
    return timeout > 0


@pytest.yield_fixture
def k():
    knitter = Knit(nn_port=8020, rm_port=8088)
    yield knitter


def test_port():
    with pytest.raises(HDFSConfigException):
        Knit(nn_port=90000, rm_port=90000)
    with pytest.raises(HDFSConfigException):
        Knit(nn_port=90000, rm_port=8088)
    with pytest.raises(HDFSConfigException):
        Knit(nn_port=9000, rm_port=5000)

    if inside_docker:
        # should pass without incident
        Knit(nn_port=8020, rm_port=8088)


def test_hostname(k):
    with pytest.raises(HDFSConfigException):
        Knit(nn="foobarbiz")
    with pytest.raises(HDFSConfigException):
        Knit(rm="foobarbiz")

    if inside_docker:
        # should pass without incident
        Knit(nn="localhost")
        k = Knit(autodetect=True)
        str(k) == 'Knit<NN=localhost:8020;RM=localhost:8088>'


def test_argument_parsing(k):
    cmd = "sleep 10"
    with pytest.raises(KnitException):
        k.start(cmd, files='a,b,c')

    with pytest.raises(KnitException):
        k.start(cmd, memory='128')


def test_cmd(k):
    cmd = "python -c 'import socket; print(socket.gethostname()*2)'"
    k.start(cmd, memory=128)

    if not k.wait_for_completion(30):
        k.kill()

    hostname = socket.gethostname() * 2
    logs = k.logs(shell=True)
    print(logs)

    assert hostname in logs, logs


def test_multiple_containers(k):
    cmd = "sleep 30"
    k.start(cmd, num_containers=2)

    wait_for_status(k, 'RUNNING')

    got_containers = wait_for_containers(k, 3)

    # wait for job to finish
    if not k.wait_for_completion(30):
        k.kill()

    if not got_containers:
        logs = k.logs(shell=True)
        print(logs)

    assert got_containers


def test_add_remove_containers(k):
    cmd = "sleep 60"
    k.start(cmd, num_containers=1)

    wait_for_status(k, 'RUNNING')

    got_containers = wait_for_containers(k, 2)

    containers = k.get_containers()
    assert len(containers) == 2

    k.add_containers(num_containers=1)

    got_more_containers = wait_for_containers(k, 3)

    containers = k.get_containers()
    assert len(containers) == 3
    k.remove_containers(containers[1])

    got_more_containers = wait_for_containers(k, 2)
    containers = k.get_containers()
    assert len(containers) == 2

    # wait for job to finish
    if not k.wait_for_completion(30):
        k.kill()

    if not (got_containers and got_more_containers):
        logs = k.logs(shell=True)
        print(logs)

    assert got_containers and got_more_containers


def test_memory(k):
    cmd = "sleep 10"
    k.start(cmd, num_containers=2, memory=300)

    wait_for_status(k, 'RUNNING')

    time.sleep(2)
    status = k.status()

    # not exactly sure on getting an exact number
    # 300*2+128(AM)
    assert status['app']['allocatedMB'] >= 728, status['app']['allocatedMB']

    # wait for job to finish
    if not k.wait_for_completion(30):
        k.kill()


def test_cmd_w_conda_env(k):
    env_zip = k.create_env(env_name='dev', packages=['python=2.6'], remove=True)
    cmd = "$PYTHON_BIN -c 'import sys; print(sys.version_info); import random; print(str(random.random()))'"
    k.start(cmd, env=env_zip)

    if not k.wait_for_completion(30):
        k.kill()

    logs = k.logs(shell=True)
    assert "(2, 6, 9, 'final', 0)" in logs, logs


cur_dir = os.path.dirname(__file__)
txt_file = os.path.join(cur_dir, 'files', 'upload_file.txt')
py_file = os.path.join(cur_dir, 'files', 'read_uploaded.py')


def test_file_uploading(k):
    cmd = 'python ./read_uploaded.py'
    k.start(cmd, files=[txt_file, py_file])

    if not k.wait_for_completion(30):
        k.kill()

    logs = k.logs(shell=True)
    assert "rambling on" in logs, logs


def test_kill_status(k):
    cmd = "sleep 10"
    k.start(cmd, num_containers=1)

    wait_for_status(k, 'RUNNING')

    assert k.kill()

    status = k.runtime_status()
    assert status == 'KILLED'


def test_yarn_kill_status(k):
    cmd = "sleep 10"
    app_id = k.start(cmd, num_containers=1)

    wait_for_status(k, 'RUNNING')

    assert k.yarn_api.kill(app_id)

    status = k.runtime_status()
    assert status == 'KILLED'


def test_logs(k):
    cmd = "sleep 10"
    k.start(cmd, num_containers=1)

    wait_for_status(k, 'RUNNING')

    assert k.logs()

    if not k.wait_for_completion(30):
        k.kill()


# temporarily removing test until vCore handling is better resolved in the core
# def test_vcores(k):
#     cmd = "sleep 10"
#     appId = k.start(cmd, num_containers=1, memory=300, virtual_cores=2)
#
#     time.sleep(2)
#     status = k.status(appId)
#
#     while status['app']['state'] != 'RUNNING':
#         status = k.status(appId)
#         time.sleep(2)
#
#     time.sleep(2)
#     status = k.status(appId)
#
#     assert status['app']['allocatedVCores'] == 3
#
