#!/usr/bin/python
import json
import shlex
from os.path import expanduser, join
import os 
import sys
import subprocess
import Queue
import threading

KEY_INFO_FILE = join(expanduser('~'), '.cvl_key_manager.cfg')

def loadKeyInfo():
    if not os.path.exists(KEY_INFO_FILE): return []
    # FIXME sanitise
    return [tuple(x) for x in json.load(open(KEY_INFO_FILE, 'r'))]


class mountUtility():

    class MountedException(Exception):
        def __init__(self, keyInfo, *args, **kw):
            super(mountUtility.MountedException, self).__init__(*args, **kw)
            self.keyInfo = keyInfo

    class SshfsException(Exception):
        def __init__(self, keyInfo, *args, **kw):
            super(mountUtility.SshfsException, self).__init__(*args, **kw)
            self.keyInfo = keyInfo

    class NotADirectoryException(Exception):
        def __init__(self, keyInfo, *args, **kw):
            super(mountUtility.NotADirectoryException, self).__init__(*args, **kw)
            self.keyInfo = keyInfo

    def __init__(self,mountTuple):
        self.username=mountTuple[1]
        self.host = mountTuple[0]
        self.localMntpt = mountTuple[2]
        self.remoteMntpt =mountTuple[3]
        self.keyInfo=mountTuple


    def isMounted(self):
        localMntpt = os.path.expanduser(self.localMntpt)
        return os.path.isMount(localMntpt)

    def uMount(self):
        try:
            localMntpt = os.path.expanduser(self.localMntpt)
            umount_cmd='/bin/fusermount -u {localMntpt}/ '.format(localMntpt=localMntpt)
            if sys.platform.startswith("win"):
                pass
            else:
                umount_cmd = shlex.split(umount_cmd)
            umountProcess = subprocess.Popen(umount_cmd,
                universal_newlines=True,shell=False,stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
            (stdout,stderr)=umountProcess.communicate()
            if stderr != "":
                raise Exception("%s"%stderr)
        except Exception as e:
            raise e
            

    def doMount(self):
        try:
            localMntpt = os.path.expanduser(self.localMntpt)
            if (not os.path.exists(localMntpt)):
                os.makedirs(localMntpt)
            else:
                if (not os.path.isdir(localMntpt)):
                    raise mountUtility.NotADirectoryException(self.keyInfo,"{localMntpt} is not a directory. Try configuring a different Local mount point for {username}@{host}".format(localMntpt=self.localMntpt,username=self.username,host=self.host))
        except OSError as e:
            raise mountUtility.NotADirectoryException(self.keyInfo,"\"{localMntpt}\" Could not be used as the local mount point. Try entering a different value for the Local mount point.".format(localMntpt=self.localMntpt))
            
        if (os.path.ismount(localMntpt)):
                raise mountUtility.MountedException(self.keyInfo,"already mounted")
        sshfs_cmd='sshfs -o Ciphers=arcfour {username}@{host}:{remoteMntpt} {localMntpt}'.format(username=self.username,host=self.host,remoteMntpt=os.path.expanduser(self.remoteMntpt),localMntpt=localMntpt)
        # Not 100% sure if this is necessary on Windows vs Linux. Seems to break the
        # Windows version of the launcher, but leaving in for Linux/OSX.
        if sys.platform.startswith("win"):
            pass
        else:
            sshfs_cmd = shlex.split(sshfs_cmd)

        sshfsProcess = subprocess.Popen(sshfs_cmd,
            universal_newlines=True,shell=False,stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
        (stdout,stderr)=sshfsProcess.communicate()
        if stderr != "":
            raise mountUtility.SshfsException(self.keyInfo,"%s"%stderr)


def runCommandline():

    for mount in loadKeyInfo():
        mu=mountUtility(mount)
        try:
            mu.doMount()
        except mountUtility.MountedException as e:
            pass
        except mountUtility.NotADirectoryException as e:
            print e.args
        except OSError as e:
            print e.__str__()
        except Exception as e:
            print e.__str__()

if __name__ == '__main__':
    runCommandline()
