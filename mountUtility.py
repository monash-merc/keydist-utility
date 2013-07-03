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

    class NotADirectoryException(Exception):
        def __init__(self, keyInfo, *args, **kw):
            super(mountUtility.NotADirectoryException, self).__init__(*args, **kw)
            self.keyInfo = keyInfo

    def __init__(self,mountTuple):
        self.username=mountTuple[1]
        self.host = mountTuple[0]
        self.localMntpt = mountTuple[2]
        self.remoteMntpt = mountTuple[3]


    def doMount(self):
        print "in doMount"
        try:
            if (not os.path.exists(self.localMntpt)):
                os.makedirs(self.localMntpt)
            else:
                if (not os.path.isdir(self.localMntpt)):
                    raise mountUtility.NotADirectoryException((self.host, self.username, self.localMntpt, self.remoteMntpt,),"{localMntpt} is not a directory. Try configuring a different Local mount point for {username}@{host}".format(localMntpt=self.localMntpt,username=self.username,host=self.host))
        except OSError as e:
            raise mountUtility.NotADirectoryException((self.host, self.username, self.localMntpt, self.remoteMntpt,),"\"{localMntpt}\" Could not be used as the local mount point. Try entering a different value for the Local mount point.".format(localMntpt=self.localMntpt))
            
        if (os.path.ismount(self.localMntpt)):
                print "trying to raise a mounted exception"
                raise mountUtility.MountedException((self.host, self.username, self.localMntpt, self.remoteMntpt,),"already mounted")
        sshfs_cmd='sshfs -o Ciphers=arcfour {username}@{host}:{remoteMntpt} {localMntpt}'.format(username=self.username,host=self.host,remoteMntpt=self.remoteMntpt,localMntpt=self.localMntpt)
        # Not 100% sure if this is necessary on Windows vs Linux. Seems to break the
        # Windows version of the launcher, but leaving in for Linux/OSX.
        if sys.platform.startswith("win"):
            pass
        else:
            sshfs_cmd = shlex.split(sshfs_cmd)

        sshfsProcess = subprocess.Popen(sshfs_cmd,
            universal_newlines=True,shell=False,stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=None)
        (stdout,stderr)=sshfsProcess.communicate()


def runCommandline():

    for mount in loadKeyInfo():
        mu=mountUtility(mount)
        try:
            mu.doMount()
        except mountUtility.MountedException as e:
            print "already mounted"
            pass
        except mountUtility.NotADirectoryException as e:
            print "Not a dir exception"
            print e.args
        except OSError as e:
            print "Oserror exception"
            print e.__str__()
        except Exception as e:
            print "other exception"
            print e.__str__()
            pass

if __name__ == '__main__':
    runCommandline()
