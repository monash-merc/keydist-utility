# Help with scrolled panel thanks to: http://stackoverflow.com/questions/7795726/scrolledpanel-inside-panel-not-sizing

import json
import wx
import wx.lib.scrolledpanel as scrolled
import  wx.lib.newevent

from os.path import expanduser, join
import os 

import sshKeyDist
import time

KEY_INFO_FILE = join(expanduser('~'), '.cvl_key_manager.cfg')

def uniq(x):
    return sorted(dict(zip(x, [True]*len(x))).keys())

def loadKeyInfo():
    if not os.path.exists(KEY_INFO_FILE): return []

    # FIXME sanitise

    return [tuple(x) for x in json.load(open(KEY_INFO_FILE, 'r'))]
 
def saveKeyInfo(keyInfo):
    json.dump(keyInfo, open(KEY_INFO_FILE, 'w'), sort_keys=True, indent=4, separators=(',', ': '))

EvtRedrawKeytable, EVT_REDRAW_KEYTABLE = wx.lib.newevent.NewEvent()

class AddHostDialog(wx.Dialog):
    def __init__(self):
        wx.Dialog.__init__(self, None, -1, 'Add Host', style=wx.DEFAULT_DIALOG_STYLE|wx.THICK_FRAME|wx.RESIZE_BORDER|wx.TAB_TRAVERSAL)

        self.addHostSizer = wx.FlexGridSizer(rows=4, cols=2, vgap=5, hgap=10)

        self.hostLabel = wx.StaticText(self, wx.ID_ANY, 'Hostname:')
        self.addHostSizer.Add(self.hostLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.hostnameText = wx.TextCtrl(self, wx.ID_ANY, '', size=(200, -1))
        self.addHostSizer.Add(self.hostnameText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.usernameLabel = wx.StaticText(self, wx.ID_ANY, 'Username:')
        self.addHostSizer.Add(self.usernameLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.usernameText = wx.TextCtrl(self, wx.ID_ANY, '', size=(200, -1))
        self.addHostSizer.Add(self.usernameText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.localMountPointLabel = wx.StaticText(self, wx.ID_ANY, 'Local mount point:')
        self.addHostSizer.Add(self.localMountPointLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.localMountPointText = wx.TextCtrl(self, wx.ID_ANY, '', size=(200, -1))
        self.addHostSizer.Add(self.localMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.remoteMountPointLabel = wx.StaticText(self, wx.ID_ANY, 'Remote mount point:')
        self.addHostSizer.Add(self.remoteMountPointLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

        self.remoteMountPointText = wx.TextCtrl(self, wx.ID_ANY, '', size=(200, -1))
        self.addHostSizer.Add(self.remoteMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)

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
        self.SetFocus()

    def onClose(self, event):
        self.Destroy()

    def onOK(self, event):
        # FIXME sanity check hostname, username, etc.
        hostName            = self.hostnameText.GetValue()
        userName            = self.usernameText.GetValue()
        localMountPoint     = self.localMountPointText.GetValue()
        remoteMountPoint    = self.remoteMountPointText.GetValue()

        self.keyManagerFrame.distributeKey(hostName, userName)

        # FIXME Should only do this on success...
        self.keyManagerFrame.keyInfo.append((hostName, userName, 'keyFileNameFIXME', localMountPoint, remoteMountPoint,))
        print self.keyManagerFrame.keyInfo
        self.keyManagerFrame.keyInfo = uniq(self.keyManagerFrame.keyInfo)

        wx.PostEvent(self.keyManagerFrame.GetEventHandler(), EvtRedrawKeytable())
        self.Destroy()
        saveKeyInfo(self.keyManagerFrame.keyInfo)

        

class KeyManagerFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, "CVL Key Manager", size=(1000,500))

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
        panelSizer.AddSpacer(50)
        panelSizer.Add(self.scrolled_panel, 1, wx.EXPAND)
        panelSizer.Add(bottomButtonPanelSizer, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_RIGHT)
        self.panel.SetSizer(panelSizer)
        self.Centre()

        self.Bind(EVT_REDRAW_KEYTABLE, self.drawKeytableSizer)

        try:
            os.mkdir(os.path.join(expanduser('~'), '.ssh'))
        except:
            pass
        os.chmod(os.path.join(expanduser('~'), '.ssh'), 0700)

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

        for (hostname, username, keyFileName, localMountPoint, remoteMountPoint,) in sorted(self.keyInfo):
            hostLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, hostname)
            self.keySizer.Add(hostLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(hostLabel)

            usernameLabel = wx.StaticText(self.scrolled_panel, wx.ID_ANY, username)
            self.keySizer.Add(usernameLabel, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(usernameLabel)

            localMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, localMountPoint)
            self.keySizer.Add(localMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(localMountPointText)

            remoteMountPointText = wx.StaticText(self.scrolled_panel, wx.ID_ANY, remoteMountPoint)
            self.keySizer.Add(remoteMountPointText, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(remoteMountPointText)

            button = wx.Button(self.scrolled_panel, self.button_id, 'Reinstall')
            button.keyInfo = (hostname, username, keyFileName,)
            button.Bind(wx.EVT_BUTTON, self.onReinstall)
            self.keySizer.Add(button, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(button)
            self.button_id += 1

            button = wx.Button(self.scrolled_panel, self.button_id, 'Delete')
            button.Bind(wx.EVT_BUTTON, self.onDelete)

            button.keyInfo = (hostname, username, keyFileName, localMountPoint, remoteMountPoint,)
            self.keySizer.Add(button, flag=wx.TOP|wx.BOTTOM|wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=10)
            self.widgets.append(button)
            self.button_id += 1

        self.scrolled_panel.SetSizer(self.keySizer)
        self.scrolled_panel.Update()
        self.panel.Update()

        self.scrolled_panel.Layout()
        self.scrolled_panel.SetupScrolling()

    def distributeKey(self, hostName, userName):
        sshPaths = sshKeyDist.sshpaths()
        skd = sshKeyDist.KeyDist(userName, hostName, self, sshPaths)
        skd.distributeKey()
        while (not skd.complete()):
            wx.Yield()
            time.sleep(1) # FIXME testing, change back to 0.1
            print 'sleeping...'
        print 'done!'
        # FIXME need an event here for timeout, successful key install, etc.

    def onAdd(self, event):
        # FIXME testing only
        # hostname = str(self.button_id)
        # username = str(self.button_id)
        dlg = AddHostDialog()
        dlg.keyManagerFrame = self
        dlg.ShowModal()
        dlg.Destroy()

        self.drawKeytableSizer()

    def onDelete(self, event):
        self.keyInfo = [z for z in self.keyInfo if z != event.GetEventObject().keyInfo]
        saveKeyInfo(self.keyInfo)
        # FIXME delete the local key.
        # FIXME delete the remote key?
        self.drawKeytableSizer()

    def onReinstall(self, event):
        (hostname, username, _) = event.GetEventObject().keyInfo

        self.distributeKey(hostname, username)

if __name__ == '__main__':
    app = wx.App(False)
    frame = KeyManagerFrame().Show()
    app.MainLoop()




