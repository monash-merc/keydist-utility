#!/usr/bin/env python

# Help with scrolled panel thanks to: http://stackoverflow.com/questions/7795726/scrolledpanel-inside-panel-not-sizing

import json
import wx
import wx.lib.scrolledpanel as scrolled
import  wx.lib.newevent

from os.path import expanduser, join
import os 

import cvlsshutils.sshKeyDist
import time
import threading
import Queue
import mountUtility

# import launcher_progress_dialog

import utilityFunctions
utilityFunctions.configureLogger('keydist-utility')

KEY_INFO_FILE = join(expanduser('~'), '.sshfs_mounts.cfg')
# list of paths to search for a config file specifing command hosts to mount.
DEFAULT_SITES_FILES= ['/etc/sshfs_default_sites.cfg',join(os.getcwd(),'.sshfs_default_sites.cfg'),join(expanduser('~'),'.sshfs_default_sites.cfg')]

def loadSites():
    cfg={}
    for cfgfile in DEFAULT_SITES_FILES:
        if os.path.exists(cfgfile):
            cfg.update(json.load(open(cfgfile,'r')))
    return cfg

def uniq(x):
    return sorted(dict(zip(x, [True]*len(x))).keys())

def loadKeyInfo():
    if not os.path.exists(KEY_INFO_FILE): return []

    # FIXME sanitise

    return [tuple(x) for x in json.load(open(KEY_INFO_FILE, 'r'))]
 
def saveKeyInfo(keyInfo):
    json.dump(keyInfo, open(KEY_INFO_FILE, 'w'), sort_keys=True, indent=4, separators=(',', ': '))

def isValidHostname(h):
    return all([x.isalnum() or x in ['-', '.'] for x in h])

def isValidUsername(u):
    # FIXME check this
    return all([x.isalnum() or x in ['-', '.'] for x in u])

EvtRedrawKeytable,          EVT_REDRAW_KEYTABLE             = wx.lib.newevent.NewEvent()
EvtCancelKeyDistribution,   EVT_CANCEL_KEY_DISTRIBUTION     = wx.lib.newevent.NewEvent()
EvtSaveKeyInfo,             EVT_SAVE_KEY_INFO               = wx.lib.newevent.NewEvent()
EvtCheckThreads,            EVT_CHECK_THREADS               = wx.lib.newevent.NewEvent()

# These events take an argume, so we create a NewEventType and redefine the constructor
#EVT_DO_MOUNT                    = wx.lib.newevent.NewEventType()
#EVT_REEDIT_KEY_INFO             = wx.lib.newevent.NewEventType()
EVT_DO_MOUNT_TYPE = wx.NewEventType()
EVT_DO_UMOUNT_TYPE = wx.NewEventType()
EVT_REEDIT_KEY_INFO_TYPE = wx.NewEventType()
EVT_CHECK_THREADS_TYPE = wx.NewEventType()
EVT_DO_MOUNT                    = wx.PyEventBinder(EVT_DO_MOUNT_TYPE)
EVT_DO_UMOUNT                    = wx.PyEventBinder(EVT_DO_UMOUNT_TYPE)
EVT_REEDIT_KEY_INFO             = wx.PyEventBinder(EVT_REEDIT_KEY_INFO_TYPE)
EVT_CHECK_THREADS               = wx.PyEventBinder(EVT_CHECK_THREADS_TYPE)

class EvtDoMount(wx.PyCommandEvent):
    def __init__(self,arg=None):
            wx.PyCommandEvent.__init__(self,EVT_DO_MOUNT_TYPE)
            self.arg = arg

class EvtDoUMount(wx.PyCommandEvent):
    def __init__(self,arg=None):
            wx.PyCommandEvent.__init__(self,EVT_DO_UMOUNT_TYPE)
            self.arg = arg

class EvtReeditKeyInfo(wx.PyCommandEvent):
    def __init__(self,keyInfo=None):
            wx.PyCommandEvent.__init__(self,EVT_REEDIT_KEY_INFO_TYPE)
            self.keyInfo = keyInfo

class EvtCheckThreads(wx.PyCommandEvent):
    def __init__(self,thread=None):
            wx.PyCommandEvent.__init__(self,EVT_CHECK_THREADS_TYPE)
            self.thread = thread


class sshKeyDistDisplayStringsKeyDistUtil():
    def __init__(self):
        self.passwdPrompt="""Please enter the password for your account on {host}."""
        self.passwdPromptIncorrect="Sorry, that password was incorrect"+self.passwdPrompt
        self.passphrasePrompt="Please enter the passphrase for your SSH key"
        self.passphrasePromptIncorrect="""I didn't expect to be displaying this dialog. Sorry, that passphrase was incorrect."""+self.passphrasePrompt
        self.newPassphrase="""I didn't expect to be displaying this dialog. Please enter a new passphrase"""
        self.newPassphraseEmptyForbiden="Sorry, empty passphrases are forbiden.\n"+self.newPassphrase
        self.newPassphraseTooShort="Sorry, the passphrase must be at least six characters.\n"+self.newPassphrase
        self.newPassphraseMismatch="Sorry, the two passphrases you entered don't match.\n"+self.newPassphrase
        self.newPassphraseTitle="Please enter a new Passphrase"

class exceptionHandlingThread(threading.Thread):

    def __init__(self,task,args):
        threading.Thread.__init__(self)
        self.task=task
        self.args=args
        self.Queue = Queue.Queue()
        self.callback=None

    def setCallback(self,callback):
        self.callback=callback


    def run(self):
        try:
            if self.args!= None:
                self.task(self.args)
            else:
                self.task()
        except Exception as e:
            self.Queue.put(e)
        if (self.callback != None):
            self.callback()

class AddHostDialog(wx.Dialog):
    def __init__(self,host=None,username=None,localMntpt=None,remoteMntpt=None,hideDefaults=True):
        wx.Dialog.__init__(self, None, -1, 'Add Host', style=wx.DEFAULT_DIALOG_STYLE|wx.THICK_FRAME|wx.RESIZE_BORDER|wx.TAB_TRAVERSAL)
        self.hideDefaults=hideDefaults

        #self.addHostSizer = wx.FlexGridSizer(rows=5, cols=2, vgap=5, hgap=10)
        self.addHostSizer = wx.BoxSizer(wx.VERTICAL)

        self.hostPanel=wx.Panel(self)
        self.hostPanelSizer=wx.BoxSizer(wx.HORIZONTAL)
        self.hostPanelFieldsSizer=wx.BoxSizer(wx.VERTICAL)
        self.hostPanel.SetSizer(self.hostPanelSizer)
        self.addHostSizer.Add(self.hostPanel,proportion=1,flag=wx.EXPAND)

        self.hostLabel = wx.StaticText(self.hostPanel, wx.ID_ANY,'Hostname:')
        self.hostPanelSizer.Add(self.hostLabel,proportion=1,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_LEFT|wx.EXPAND, border=10)
        self.hostPanelSizer.Add(self.hostPanelFieldsSizer,proportion=0,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT, border=10)

        
        self.sitesList={}
        self.sitesList.update(loadSites())
        default=None
        if (host != None):
            for key in self.sitesList.keys():
                val = self.sitesList[key]
                if (val['fqdn'] == host):
                    default=key
        if default !=None:
            self.hostnameComboBox=wx.ComboBox(self.hostPanel, wx.ID_ANY, value=default,choices=self.sitesList.keys(), style=wx.CB_READONLY,size=(200,-1))
        else:
            self.hostnameComboBox=wx.ComboBox(self.hostPanel, wx.ID_ANY, choices=self.sitesList.keys(), style=wx.CB_READONLY,size=(200,-1))
        self.hostnameComboBox.Bind(wx.EVT_COMBOBOX,self.comboBox)
        self.hostPanelFieldsSizer.Add(self.hostnameComboBox)

        self.hostnameText = wx.TextCtrl(self.hostPanel, wx.ID_ANY, '', size=(200, -1))
        if (host!=None):
            self.hostnameText.SetValue(host)
        self.hostPanelFieldsSizer.Add(self.hostnameText,flag=wx.TOP,border=2)


        self.usernamePanel=wx.Panel(self)
        self.usernamePanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.usernamePanel.SetSizer(self.usernamePanelSizer)
        self.addHostSizer.Add(self.usernamePanel,flag=wx.EXPAND)

        self.usernameLabel = wx.StaticText(self.usernamePanel, wx.ID_ANY, 'Username:')
        self.usernamePanelSizer.Add(self.usernameLabel, proportion=1,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_LEFT|wx.EXPAND, border=10)

        self.usernameText = wx.TextCtrl(self.usernamePanel, wx.ID_ANY, '', size=(200, -1))
        if (username !=None):
            self.usernameText.SetValue(username)
        self.usernamePanelSizer.Add(self.usernameText, proportion=0,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT|wx.EXPAND, border=10)


        self.localMountPointPanel = wx.Panel(self)
        self.localMountPointPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.localMountPointPanel.SetSizer(self.localMountPointPanelSizer)
        self.addHostSizer.Add(self.localMountPointPanel,flag=wx.EXPAND)

        self.localMountPointLabel = wx.StaticText(self.localMountPointPanel, wx.ID_ANY, 'Local mount point:')
        self.localMountPointPanelSizer.Add(self.localMountPointLabel, proportion=1,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_LEFT|wx.EXPAND, border=10)

        self.localMountPointText = wx.TextCtrl(self.localMountPointPanel, wx.ID_ANY, '', size=(200, -1))
        if (localMntpt!=None):
            self.localMountPointText.SetValue(localMntpt)
        self.localMountPointPanelSizer.Add(self.localMountPointText, proportion=0,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT|wx.EXPAND, border=10)



        self.remoteMountPointPanel = wx.Panel(self)
        self.remoteMountPointPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.remoteMountPointPanel.SetSizer(self.remoteMountPointPanelSizer)
        self.addHostSizer.Add(self.remoteMountPointPanel,flag=wx.EXPAND)

        self.remoteMountPointLabel = wx.StaticText(self.remoteMountPointPanel, wx.ID_ANY, 'Remote mount point:')
        self.remoteMountPointPanelSizer.Add(self.remoteMountPointLabel, proportion=1,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_LEFT|wx.EXPAND, border=10)

        self.remoteMountPointText = wx.TextCtrl(self.remoteMountPointPanel, wx.ID_ANY, '', size=(200, -1))
        if (remoteMntpt!=None):
            self.remoteMountPointText.SetValue(remoteMntpt)
        self.remoteMountPointPanelSizer.Add(self.remoteMountPointText, proportion=0,flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT|wx.EXPAND, border=10)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        okButton = wx.Button(self, label='Add')
        okButton.Bind(wx.EVT_BUTTON, self.onOK)

        closeButton = wx.Button(self, label='Cancel')
        closeButton.Bind(wx.EVT_BUTTON, self.onClose)

        hbox.Add(okButton)
        hbox.Add(closeButton)

        topSizer = wx.BoxSizer(wx.VERTICAL)
        # topSizer.AddSpacer(50)
        topSizer.Add(self.addHostSizer, 1, wx.EXPAND)
        topSizer.Add(hbox, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT)

        self.SetSizer(topSizer)
        self.CentreOnParent(wx.BOTH)
        self.Fit()
        self.SetFocus()
        if (self.hostnameComboBox.GetValue() == ""):
            if (len(self.sitesList.keys())>0):
                self.hostnameComboBox.SetValue(self.sitesList.keys()[0])
                # We have no way of knowing what sites have been configured, but if Other is an option we'd rather not use that as the default
                if (self.hostnameComboBox.GetValue() == "Other" or self.hostnameComboBox.GetValue() == "other" and len(self.sitesList.keys()) > 1):
                    self.hostnameComboBox.SetValue(self.sitesList.keys()[1])
                self.setAndHide(self.hostnameComboBox.GetValue())

    def setAndHide(self,val):
        if (self.sitesList[val].has_key("fqdn")):
            self.hostnameText.SetValue(self.sitesList[val]["fqdn"])
        if (self.sitesList[val].has_key("lmntpt")):
            self.localMountPointText.SetValue(self.sitesList[val]["lmntpt"])
        if (self.sitesList[val].has_key("rmntpt")):
            self.remoteMountPointText.SetValue(self.sitesList[val]["rmntpt"])
        if (self.hideDefaults):
            if (self.hostnameText.GetValue() == ""):
                self.hostnameText.Show()
            else:
                self.hostnameText.Hide()
            if (self.localMountPointText.GetValue() == ""):
                self.localMountPointPanel.Show()
            else:
                self.localMountPointPanel.Hide()
            if (self.remoteMountPointText.GetValue() == ""):
                self.remoteMountPointPanel.Show()
            else:
                self.remoteMountPointPanel.Hide()
        self.Fit()

    def comboBox(self,event):
        val=event.GetEventObject().GetValue()
        self.setAndHide(val)

    def onClose(self, event):
        wx.CallAfter(self.keyManagerFrame.statusBar.SetStatusText, '')
        self.Destroy()

    def onOK(self, event):
        # FIXME sanity check hostname, username, etc.
        hostName            = self.hostnameText.GetValue()
        userName            = self.usernameText.GetValue()
        localMountPoint     = self.localMountPointText.GetValue()
        remoteMountPoint    = self.remoteMountPointText.GetValue()

        userCanAbort            = True
        maximumProgressBarValue = 10

        self.keyManagerFrame.hostName           = hostName
        self.keyManagerFrame.userName           = userName
        self.keyManagerFrame.localMountPoint    = localMountPoint
        self.keyManagerFrame.remoteMountPoint   = remoteMountPoint

        if not isValidHostname(hostName):
            def showHostnameInvalidDialog():
                dlg = wx.MessageDialog(self, "Sorry, hostnames may only contain a-z, A-Z, 0-9, and periods.\n", "CVL Key Utility", wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
            wx.CallAfter(showHostnameInvalidDialog)
            return

        if not isValidUsername(userName):
            def showUsernameInvalidDialog():
                dlg = wx.MessageDialog(self, "Sorry, usernames may only contain a-z, A-Z, 0-9, and '-'.\n", "CVL Key Utility", wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
            wx.CallAfter(showUsernameInvalidDialog)
            return

        wx.CallAfter(self.keyManagerFrame.statusBar.SetStatusText, 'Configuring %s on host %s...' % (userName, hostName,))
        self.keyManagerFrame.runDistributeKey()

        self.Destroy()

class StatusBar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent)

        self.SetFieldsCount(2)
        self.SetStatusWidths([-5, -2])

class KeyManagerFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, "Remote File Manager", size=(1100,500))

        self.menu_bar = wx.MenuBar()

        self.file_menu = wx.Menu()
        self.file_menu.Append(wx.ID_ANY, "&Add\tAlt-A", "Add host.")
        self.Bind(wx.EVT_MENU, self.onAdd, id=wx.ID_ANY)
        self.file_menu.Append(wx.ID_EXIT, "E&xit\tAlt-X", "Close window and exit program.")
        self.Bind(wx.EVT_MENU, self.onExit, id=wx.ID_EXIT)
        self.menu_bar.Append(self.file_menu, "&File")

        self.help_menu = wx.Menu()
        self.help_menu.Append(wx.ID_ABOUT,   "&About Remote File Manager")
        self.Bind(wx.EVT_MENU, self.onAbout, id=wx.ID_ABOUT)
        self.menu_bar.Append(self.help_menu, "&Help")
        self.SetMenuBar(self.menu_bar)

        self.statusBar = StatusBar(self)
        self.SetStatusBar(self.statusBar)

        self.panel = wx.Panel(self, wx.ID_ANY)

        self.scrolled_panel = scrolled.ScrolledPanel(self.panel, -1, style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER, name="panel1")
        self.scrolled_panel.SetAutoLayout(1)
        self.scrolled_panel.SetupScrolling()

        self.button_id = 0
        self.widgets = []

        self.keyInfo = loadKeyInfo()

        self.drawKeytableSizer()

        btn = wx.Button(self.panel, label="Add Host")
        btn.Bind(wx.EVT_BUTTON, self.onAdd)

        bottomButtonPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        bottomButtonPanelSizer.Add(btn)

        panelSizer = wx.BoxSizer(wx.VERTICAL)
        # panelSizer.AddSpacer(50)
        panelSizer.Add(self.scrolled_panel, 1, wx.EXPAND)
        panelSizer.Add(bottomButtonPanelSizer, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT)
        self.panel.SetSizer(panelSizer)
        self.Centre()

        self.Bind(EVT_REDRAW_KEYTABLE, self.drawKeytableSizer)
        self.Bind(EVT_SAVE_KEY_INFO, self.saveKeyInfoHandler)
        self.Bind(EVT_DO_MOUNT, self.doMountHandler)
        self.Bind(EVT_DO_UMOUNT, self.doUMountHandler)
        self.Bind(EVT_CHECK_THREADS, self.checkThreadsHandler)
        self.Bind(EVT_REEDIT_KEY_INFO, self.reeditKeyInfoHandler)

        try:
            os.mkdir(os.path.join(expanduser('~'), '.ssh'))
        except:
            pass
        os.chmod(os.path.join(expanduser('~'), '.ssh'), 0700)

    def onAbout(self, event):
        pass

    def onExit(self, event):
        self.Destroy()


    def checkThreadsHandler(self,event):
        wx.EndBusyCursor()
        try:
            e = event.thread.Queue.get(block=False)
            try:
                raise e
            except mountUtility.mountUtility.MountedException as e:
                # TODO ... unmount and remount the mount point
                dlg=utilityFunctions.HelpDialog(self,pos=(200,150),size=(680,290),style=wx.STAY_ON_TOP)
                panel=wx.Panel(dlg)
                panel=wx.Panel(dlg)
                sizer=wx.BoxSizer()
                panel.SetSizer(sizer)
                msg="It looks like your trying to mount some files from a remote computer that are already mounted.\nI don't really know what you intended.\nPerhaps would would like to try setting the Hostname to Other and using some more advanced options."
                text=wx.StaticText(panel,wx.ID_ANY,label=msg)
                sizer.Add(text,0,wx.ALL,15)
                dlg.addPanel(panel)
                dlg.ShowModal()
                pass
            except mountUtility.mountUtility.NotADirectoryException as e:
                #dlg=wx.Dialog(self,style=wx.STAY_ON_TOP)
                dlg=utilityFunctions.HelpDialog(self,pos=(200,150),size=(680,290),style=wx.STAY_ON_TOP)
                panel=wx.Panel(dlg)
                panel=wx.Panel(dlg)
                sizer=wx.BoxSizer()
                panel.SetSizer(sizer)
                text=wx.StaticText(panel,wx.ID_ANY,label=e.__str__())
                sizer.Add(text,0,wx.ALL,15)
                dlg.addPanel(panel)
                dlg.ShowModal()
                
                wx.PostEvent(self.GetEventHandler(),EvtReeditKeyInfo(e.keyInfo))
                pass
            except mountUtility.mountUtility.SshfsException as e:
                dlg=utilityFunctions.HelpDialog(self,pos=(200,150),size=(680,290),style=wx.STAY_ON_TOP)
                panel=wx.Panel(dlg)
                panel=wx.Panel(dlg)
                sizer=wx.BoxSizer()
                panel.SetSizer(sizer)
                text=wx.StaticText(panel,wx.ID_ANY,label=e.__str__())
                sizer.Add(text,0,wx.ALL,15)
                dlg.addPanel(panel)
                dlg.ShowModal()
                wx.PostEvent(self.GetEventHandler(),EvtReeditKeyInfo(e.keyInfo))
                pass
            except Exception as e:
                pass
        #          raise e
        except Queue.Empty as e:
            # Let the user know that it finished.
            def showKeyDistSuccessDialog():
                dlg = wx.MessageDialog(self, "Key successfully installed.\n", "CVL Key Utility", wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
                dlg.Destroy()
            #wx.CallAfter(showKeyDistSuccessDialog)
            pass
        except Exception as e:
            raise e
        self.drawKeytableSizer()

    def reeditKeyInfoHandler(self,event):
        self.keyInfo = [z for z in self.keyInfo if z != event.keyInfo]
        wx.PostEvent(self.GetEventHandler(),EvtSaveKeyInfo())

        self.drawKeytableSizer()
        dlg = AddHostDialog(event.keyInfo[0],event.keyInfo[1],event.keyInfo[2],event.keyInfo[3],hideDefaults=False)
        dlg.keyManagerFrame = self
        dlg.ShowModal()
        dlg.Destroy()

        self.drawKeytableSizer()

    def saveKeyInfoHandler(self,event):
        t = exceptionHandlingThread(saveKeyInfo,self.keyInfo)
        t.start()

    def doMountHandler(self,event):
        mount = mountUtility.mountUtility(event.arg)
        t = exceptionHandlingThread(mount.doMount,None)
        callback=lambda: wx.PostEvent(self.GetEventHandler(),EvtCheckThreads(t))
        t.setCallback(callback)
        t.start()

    def doUMountHandler(self,event):
        mount = mountUtility.mountUtility(event.arg)
        t = exceptionHandlingThread(mount.uMount,None)
        callback=lambda: wx.PostEvent(self.GetEventHandler(),EvtCheckThreads(t))
        t.setCallback(callback)
        t.start()

    def drawKeytableSizer(self, event=None):
        self.keySizer = wx.FlexGridSizer(rows=len(self.keyInfo), cols=6, vgap=5, hgap=10)

        for w in self.widgets:
            w.Hide()
            self.keySizer.Detach(w)

        hostLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, 'Hostname')
        hostLabel.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.keySizer.Add(hostLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(hostLabel)

        usernameLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, 'Username')
        usernameLabel.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.keySizer.Add(usernameLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(usernameLabel)

        localMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, 'Local mount point')
        localMountPointText.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.keySizer.Add(localMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(localMountPointText)

        remoteMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, 'Remote mount point')
        remoteMountPointText.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.keySizer.Add(remoteMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(remoteMountPointText)

        editEmpty = wx.StaticText(self.scrolled_panel, wx.ID_ANY, '')
        self.keySizer.Add(editEmpty, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(editEmpty)

        deleteEmpty = wx.StaticText(self.scrolled_panel, wx.ID_ANY, '')
        self.keySizer.Add(deleteEmpty, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
        self.widgets.append(deleteEmpty)

        for (hostname, username, localMountPoint, remoteMountPoint,) in sorted(self.keyInfo):
            hostLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, hostname)
            self.keySizer.Add(hostLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(hostLabel)

            usernameLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, username)
            self.keySizer.Add(usernameLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(usernameLabel)

            if localMountPoint  == '':
                localMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, '<not specified>')
            else:
                localMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, localMountPoint)
            self.keySizer.Add(localMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(localMountPointText)

            if remoteMountPoint == '':
                remoteMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, '<not specified>')
            else:
                remoteMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, remoteMountPoint)
            self.keySizer.Add(remoteMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(remoteMountPointText)

            button = wx.Button(self.scrolled_panel, self.button_id, 'Mount')
            button.keyInfo = (hostname, username, localMountPoint, remoteMountPoint)
            button.Bind(wx.EVT_BUTTON, self.onMount)
            self.keySizer.Add(button, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(button)
            self.button_id += 1
            if (os.path.ismount(os.path.expanduser(localMountPoint))):
                button.Disable()
            else:
                button.Enable()
            button = wx.Button(self.scrolled_panel, self.button_id, 'Un-Mount')
            button.Bind(wx.EVT_BUTTON, self.onUnMount)

            button.keyInfo = (hostname, username, localMountPoint, remoteMountPoint,)

            if (not os.path.ismount(os.path.expanduser(localMountPoint))):
                button.Disable()
            else:
                button.Enable()
            self.keySizer.Add(button, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(button)
            self.button_id += 1

        self.scrolled_panel.SetSizer(self.keySizer)
        self.scrolled_panel.Update()
        self.panel.Update()

        self.scrolled_panel.Layout()
        self.scrolled_panel.SetupScrolling()

        self.statusBar.SetStatusText('')

    def onKeyDistSuccess(self):
        # The cvlsshutils.sshKeyDist module successfully installed the ssh key on the remove server. Yay!
        self.statusBar.SetStatusText('')

        # Append the new key/mountpoint info to our list.
        self.keyInfo.append((self.hostName, self.userName, self.localMountPoint, self.remoteMountPoint,))
        self.keyInfo = uniq(self.keyInfo)

        # Redraw the table of keypairs.
        wx.PostEvent(self.GetEventHandler(), EvtRedrawKeytable())

        # Commit the new key/mountpoint info to disk.
        wx.PostEvent(self.GetEventHandler(),EvtSaveKeyInfo())
        wx.PostEvent(self.GetEventHandler(),EvtDoMount(arg=(self.hostName, self.userName, self.localMountPoint, self.remoteMountPoint,)))


    def onKeyDistFail(self):
        self.statusBar.SetStatusText('')
        wx.EndBusyCursor()

        def showKeyDistFailDialog():
            dlg = wx.MessageDialog(self, "Did not install key.\n", "CVL Key Utility", wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
        wx.CallAfter(showKeyDistFailDialog)




    def runDistributeKey(self):
        self.statusBar.SetStatusText('Configuring %s on host %s' % (self.userName, self.hostName,))

        wx.BeginBusyCursor()

        sshPaths = cvlsshutils.sshKeyDist.sshpaths('MassiveLauncherKey')

        displayStrings = sshKeyDistDisplayStringsKeyDistUtil()

        skd = cvlsshutils.sshKeyDist.KeyDist(None,self.userName, self.hostName, self.hostName, self, sshPaths,displayStrings)
        skd.distributeKey(callback_success=self.onKeyDistSuccess, callback_fail=self.onKeyDistFail)

    def onAdd(self, event):
        dlg = AddHostDialog()
        dlg.keyManagerFrame = self
        dlg.ShowModal()
        dlg.Destroy()

        self.drawKeytableSizer()

    def onUnMount(self, event=None):
        dlg = wx.MessageDialog(self, "Would you like this filesystem to be mounted next time?\n", "CVL Key Utility", wx.YES_NO | wx.ICON_INFORMATION)
        result = dlg.ShowModal()
        if (result==wx.ID_NO):
            self.keyInfo = [z for z in self.keyInfo if z != event.GetEventObject().keyInfo]
            wx.PostEvent(self.GetEventHandler(),EvtSaveKeyInfo())
        dlg.Destroy()
        self.drawKeytableSizer()
        wx.PostEvent(self.GetEventHandler(),EvtDoUMount(arg=(event.GetEventObject().keyInfo)))

    def onMount(self, event):
        (self.hostName, self.userName, self.localMountPoint, self.remoteMountPoint) = event.GetEventObject().keyInfo
        self.runDistributeKey()
        #wx.PostEvent(self.GetEventHandler(),EvtDoMount(arg=(self.hostName, self.userName, self.localMountPoint, self.remoteMountPoint,)))

if __name__ == '__main__':
    app = wx.App(False)
    frame = KeyManagerFrame().Show()
    app.MainLoop()




