# COPYRIGHT (C) 2020 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2013 SeeSchloss <see@seos.fr>
# COPYRIGHT (C) 2009-2010 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from gettext import gettext as _
from sys import maxsize

from gi.repository import Gdk
from gi.repository import GObject as gobject
from gi.repository import Gtk as gtk

from _thread import start_new_thread
from pynicotine import slskmessages
from pynicotine.gtkgui.dirchooser import ChooseDir
from pynicotine.gtkgui.dialogs import ComboBoxDialog
from pynicotine.gtkgui.utils import HideColumns
from pynicotine.gtkgui.utils import HumanSize
from pynicotine.gtkgui.utils import InitialiseColumns
from pynicotine.gtkgui.utils import PopupMenu
from pynicotine.gtkgui.utils import SetTreeviewSelectedRow
from pynicotine.logfacility import log
from pynicotine.utils import CleanFile
from pynicotine.utils import executeCommand
from pynicotine.utils import GetUserDirectories
from pynicotine.utils import GetResultBitrateLength


class UserBrowse:

    def __init__(self, userbrowses, user, conn):
        _config_dir, self.data_dir = GetUserDirectories()

        # Build the window
        builder = gtk.Builder()

        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "userbrowse.ui"))

        self.UserBrowseTab = builder.get_object("UserBrowseTab")

        for i in builder.get_objects():
            try:
                self.__dict__[gtk.Buildable.get_name(i)] = i
            except TypeError:
                pass

        self.UserBrowseTab.remove(self.Main)
        self.UserBrowseTab.destroy()

        builder.connect_signals(self)

        self.userbrowses = userbrowses

        self.frame = userbrowses.frame
        self.user = user
        self.conn = conn

        # selected_folder is the current selected folder
        self.selected_folder = None
        self.search_list = []
        self.query = None
        self.search_position = 0
        self.selected_files = []

        self.shares = []

        # Iters for current DirStore
        self.directories = {}

        # Iters for current FileStore
        self.files = {}
        self.totalsize = 0

        self.DirStore = gtk.TreeStore(str, str)

        self.FolderTreeView.set_headers_visible(True)
        self.FolderTreeView.set_enable_tree_lines(True)

        cols = InitialiseColumns(
            self.FolderTreeView,
            [_("Directories"), -1, "text", self.CellDataFunc]  # 0
        )
        cols[0].set_sort_column_id(0)

        self.popup_menu_users = PopupMenu(self.frame, False)
        self.popup_menu_users2 = PopupMenu(self.frame, False)
        for menu in [self.popup_menu_users, self.popup_menu_users2]:
            menu.setup(
                ("#" + _("Send _message"), menu.OnSendMessage),
                ("#" + _("Show IP a_ddress"), menu.OnShowIPaddress),
                ("#" + _("Get user i_nfo"), menu.OnGetUserInfo),
                ("#" + _("Gi_ve privileges"), menu.OnGivePrivileges),
                ("", None),
                ("$" + _("_Add user to list"), menu.OnAddToList),
                ("$" + _("_Ban this user"), menu.OnBanUser),
                ("$" + _("_Ignore this user"), menu.OnIgnoreUser)
            )

        self.popup_menu_downloads_folders = PopupMenu(self.frame, False)
        self.popup_menu_downloads_folders.setup(
            ("#" + _("_Download directory"), self.OnDownloadDirectory),
            ("#" + _("Download directory _to..."), self.OnDownloadDirectoryTo),
            ("#" + _("Download _recursive"), self.OnDownloadDirectoryRecursive),
            ("#" + _("Download r_ecursive to..."), self.OnDownloadDirectoryRecursiveTo)
        )

        self.popup_menu_downloads_files = PopupMenu(self.frame, False)
        self.popup_menu_downloads_files.setup(
            ("#" + _("_Download file(s)"), self.OnDownloadFiles),
            ("#" + _("Download _to..."), self.OnDownloadFilesTo),
            ("", None),
            ("#" + _("_Download directory"), self.OnDownloadDirectory),
            ("#" + _("Download directory _to..."), self.OnDownloadDirectoryTo),
            ("#" + _("Download _recursive"), self.OnDownloadDirectoryRecursive),
            ("#" + _("Download r_ecursive to..."), self.OnDownloadDirectoryRecursiveTo)
        )

        self.popup_menu_uploads_folders = PopupMenu(self.frame, False)
        self.popup_menu_uploads_folders.setup(
            ("#" + _("Upload Directory to..."), self.OnUploadDirectoryTo),
            ("#" + _("Upload Directory recursive to..."), self.OnUploadDirectoryRecursiveTo)
        )

        self.popup_menu_uploads_files = PopupMenu(self.frame, False)
        self.popup_menu_uploads_files.setup(
            ("#" + _("Upload Directory to..."), self.OnUploadDirectoryTo),
            ("#" + _("Upload Directory recursive to..."), self.OnUploadDirectoryRecursiveTo),
            ("#" + _("Up_load file(s)"), self.OnUploadFiles)
        )

        self.folder_popup_menu = PopupMenu(self.frame)
        self.folder_popup_menu.set_user(user)

        if user == self.frame.np.config.sections["server"]["login"]:
            self.folder_popup_menu.setup(
                ("USERMENU", _("User"), self.popup_menu_users, self.OnPopupMenuFolderUser),
                ("", None),
                (1, _("Download"), self.popup_menu_downloads_folders, self.OnPopupMenuDummy),
                (1, _("Upload"), self.popup_menu_uploads_folders, self.OnPopupMenuDummy),
                ("", None),
                ("#" + _("Copy _URL"), self.OnCopyDirURL),
                ("#" + _("Open in File Manager"), self.OnFileManager)
            )
        else:
            self.folder_popup_menu.setup(
                ("USERMENU", _("User"), self.popup_menu_users, self.OnPopupMenuFolderUser),
                ("", None),
                (1, _("Download"), self.popup_menu_downloads_folders, self.OnPopupMenuDummy),
                ("", None),
                ("#" + _("Copy _URL"), self.OnCopyDirURL)
            )

        self.FolderTreeView.connect("button_press_event", self.OnFolderClicked)
        self.FolderTreeView.get_selection().connect("changed", self.OnSelectDir)

        # Filename, HSize, Bitrate, HLength, Size, Length, RawFilename
        self.FileStore = gtk.ListStore(str, str, str, str, gobject.TYPE_INT64, int, str)

        self.FileTreeView.set_model(self.FileStore)
        widths = self.frame.np.config.sections["columns"]["userbrowse_widths"]
        cols = InitialiseColumns(
            self.FileTreeView,
            [_("Filename"), widths[0], "text", self.CellDataFunc],
            [_("Size"), widths[1], "number", self.CellDataFunc],
            [_("Bitrate"), widths[2], "number", self.CellDataFunc],
            [_("Length"), widths[3], "number", self.CellDataFunc]
        )
        cols[0].set_sort_column_id(0)
        cols[1].set_sort_column_id(4)
        cols[2].set_sort_column_id(2)
        cols[3].set_sort_column_id(5)
        self.FileStore.set_sort_column_id(0, gtk.SortType.ASCENDING)

        HideColumns(cols, self.frame.np.config.sections["columns"]["userbrowse"])

        self.FileTreeView.get_selection().set_mode(gtk.SelectionMode.MULTIPLE)
        self.FileTreeView.set_headers_clickable(True)
        self.FileTreeView.set_rubber_banding(True)

        self.file_popup_menu = PopupMenu(self.frame)

        if user == self.frame.np.config.sections["server"]["login"]:
            self.file_popup_menu.setup(
                ("USERMENU", "User", self.popup_menu_users2, self.OnPopupMenuFileUser),
                ("", None),
                (1, _("Download"), self.popup_menu_downloads_files, self.OnPopupMenuDummy),
                (1, _("Upload"), self.popup_menu_uploads_files, self.OnPopupMenuDummy),
                ("", None),
                ("#" + _("Copy _URL"), self.OnCopyURL),
                ("#" + _("Send to _player"), self.OnPlayFiles),
                ("#" + _("Open in File Manager"), self.OnFileManager)
            )
        else:
            self.file_popup_menu.setup(
                ("USERMENU", "User", self.popup_menu_users2, self.OnPopupMenuFileUser),
                ("", None),
                (1, _("Download"), self.popup_menu_downloads_files, self.OnPopupMenuDummy),
                ("", None),
                ("#" + _("Copy _URL"), self.OnCopyURL)
            )

        self.FileTreeView.connect("button_press_event", self.OnFileClicked)

        self.ChangeColours()

        for name, object in list(self.__dict__.items()):
            if isinstance(object, PopupMenu):
                object.set_user(self.user)

    def OnPopupMenuDummy(self, widget):
        pass

    def ConnClose(self):
        pass

    def OnPopupMenuFileUser(self, widget):
        self.OnPopupMenuUsers(self.popup_menu_users2)

    def OnPopupMenuFolderUser(self, widget):
        self.OnPopupMenuUsers(self.popup_menu_users)

    def OnPopupMenuUsers(self, menu):

        items = menu.get_children()

        act = True
        items[0].set_sensitive(act)
        items[1].set_sensitive(act)
        items[2].set_sensitive(act)

        items[5].set_active(self.user in [i[0] for i in self.frame.np.config.sections["server"]["userlist"]])
        items[6].set_active(self.user in self.frame.np.config.sections["server"]["banlist"])
        items[7].set_active(self.user in self.frame.np.config.sections["server"]["ignorelist"])

        for i in range(3, 8):
            items[i].set_sensitive(act)

        return True

    def ChangeColours(self):
        self.frame.SetTextBG(self.SearchEntry)

        self.frame.ChangeListFont(self.FolderTreeView, self.frame.np.config.sections["ui"]["browserfont"])
        self.frame.ChangeListFont(self.FileTreeView, self.frame.np.config.sections["ui"]["browserfont"])

    def CellDataFunc(self, column, cellrenderer, model, iterator, dummy="dummy"):
        colour = self.frame.np.config.sections["ui"]["search"]
        if colour == "":
            colour = None
        cellrenderer.set_property("foreground", colour)

    def OnExpand(self, widget):

        if self.ExpandButton.get_active():
            self.FolderTreeView.expand_all()
            self.expand.set_from_icon_name("list-remove-symbolic", gtk.IconSize.BUTTON)
        else:
            self.FolderTreeView.collapse_all()
            self.expand.set_from_icon_name("list-add-symbolic", gtk.IconSize.BUTTON)

            dirs = sorted(self.directories.keys())

            if dirs != []:
                self.SetDirectory(dirs[0])
            else:
                self.SetDirectory(None)

    def OnFolderClicked(self, widget, event):

        pathinfo = widget.get_path_at_pos(event.x, event.y)

        if pathinfo is not None:

            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self.OnDownloadDirectory(widget)
                return True

            elif event.button == 3:
                return self.OnFolderPopupMenu(widget, event)

        return False

    def OnFolderPopupMenu(self, widget, event):

        act = True
        if self.selected_folder is None:
            act = False

        items = self.folder_popup_menu.get_children()
        for item in items[1:]:
            item.set_sensitive(act)

        self.folder_popup_menu.popup(None, None, None, None, event.button, event.time)

    def SelectedFilesCallback(self, model, path, iterator):
        rawfilename = self.FileStore.get_value(iterator, 6)
        self.selected_files.append(rawfilename)

    def OnFileClicked(self, widget, event):

        if event.button == 3:
            return self.OnFilePopupMenu(widget, event)

        else:
            pathinfo = widget.get_path_at_pos(event.x, event.y)

            if pathinfo is None:
                widget.get_selection().unselect_all()

            elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self.selected_files = []
                self.FileTreeView.get_selection().selected_foreach(self.SelectedFilesCallback)
                self.OnDownloadFiles(widget)
                self.FileTreeView.get_selection().unselect_all()
                return True

        return False

    def OnFilePopupMenu(self, widget, event):

        SetTreeviewSelectedRow(widget, event)

        self.selected_files = []
        self.FileTreeView.get_selection().selected_foreach(self.SelectedFilesCallback)

        files = True
        multiple = False

        if len(self.selected_files) > 1:
            multiple = True

        if len(self.selected_files) >= 1:
            files = True
        else:
            files = False

        items = self.file_popup_menu.get_children()

        if self.user == self.frame.np.config.sections["server"]["login"]:
            items[2].set_sensitive(files)  # Downloads
            items[3].set_sensitive(files)  # Uploads
            items[5].set_sensitive(not multiple and files)  # Copy URL
            items[6].set_sensitive(files)  # Send to player
        else:
            items[2].set_sensitive(files)  # Downloads
            items[4].set_sensitive(not multiple and files)  # Copy URL

        self.FileTreeView.stop_emission_by_name("button_press_event")
        self.file_popup_menu.popup(None, None, None, None, event.button, event.time)

        return True

    def MakeNewModel(self, list):

        self.shares = list
        self.selected_folder = None
        self.selected_files = []
        self.directories.clear()
        self.files.clear()
        self.DirStore.clear()

        # Compute the number of shared dirs and total size
        self.totalsize = 0
        for dir, files in self.shares:
            for filedata in files:
                if filedata[2] < maxsize:
                    self.totalsize += filedata[2]
                else:
                    pass

        self.AmountShared.set_text(_("Shared: %s") % HumanSize(self.totalsize))
        self.NumDirectories.set_text(_("Dirs: %s") % len(self.shares))

        # Generate the directory tree and select first directory
        currentdir = self.BrowseGetDirs()

        sel = self.FolderTreeView.get_selection()
        sel.unselect_all()
        if currentdir in self.directories:
            path = self.DirStore.get_path(self.directories[currentdir])
            if path is not None:
                sel.select_path(path)

        self.FolderTreeView.set_sensitive(True)
        self.FileTreeView.set_sensitive(True)
        self.SaveButton.set_sensitive(True)

        if self.ExpandButton.get_active():
            self.FolderTreeView.expand_all()
        else:
            self.FolderTreeView.collapse_all()

    def BrowseGetDirs(self):

        directory = ""
        dirseparator = '\\'

        # If there is no share

        if self.shares == []:

            # Set the model of the treeviex
            self.FolderTreeView.set_model(self.DirStore)

            # Sort the DirStore
            self.DirStore.set_sort_column_id(0, gtk.SortType.ASCENDING)

            return directory

        def builddicttree(p, s):
            """
                Build recursively a hierarchical dict containing raw subdir
                'p' is a reference to the parent
                's' a list of the subdir of a path

                ex of 's': ['music', 'rock', 'doors']
            """

            if s:
                subdir = s.pop(0)

                if subdir not in p:
                    p[subdir] = {}

                builddicttree(p[subdir], s)

        def buildgtktree(dictdir, parent, path):
            """
                Build recursively self.directories with iters pointing to directories
                'dictdir' is a hierarchical dict containing raw subdir
                'parent' is the iter pointing to the parent
                'path' is the current raw path
            """

            # Foreach subdir
            for subdir in dictdir:

                if parent is None:
                    # The first sudirs are attached to the root (None)
                    current_path = subdir
                else:
                    # Other sudirs futher down the path are attached to their parent
                    current_path = dirseparator.join([path, subdir])

                self.directories[current_path] = self.DirStore.append(parent, [subdir, current_path])

                # If there are subdirs futher down the path: recurse
                if len(dictdir[subdir]):
                    buildgtktree(dictdir[subdir], self.directories[current_path], current_path)

        # For each shared dir we will complete the dictionnary
        dictdir = {}

        for dirshares, f in self.shares:

            # Split the path
            s = dirshares.split(dirseparator)

            # and build a hierarchical dictionnary containing raw subdir
            if len(s) >= 1:
                builddicttree(dictdir, s)

        # Append data to the DirStore
        buildgtktree(dictdir, None, None)

        # Select the first directory
        sortlist = sorted(self.directories.keys())

        directory = sortlist[0]

        # Sort the DirStore
        self.DirStore.set_sort_column_id(0, gtk.SortType.ASCENDING)

        # Set the model of the treeviex
        self.FolderTreeView.set_model(self.DirStore)

        return directory

    def SetDirectory(self, directory):

        self.selected_folder = directory
        self.FileStore.clear()
        self.files.clear()

        found_dir = False

        for d, f in self.shares:
            if d == directory:
                found_dir = True
                files = f
                break

        if not found_dir:
            return

        for file in files:
            # Filename, HSize, Bitrate, HLength, Size, Length, RawFilename
            rl = 0

            try:
                size = int(file[2])

                # Some clients send incorrect file sizes
                if size < 0 or size > maxsize:
                    size = 0
            except ValueError:
                size = 0

            f = [file[1], HumanSize(size)]

            h_bitrate, bitrate, h_length = GetResultBitrateLength(size, file[4])
            f += [h_bitrate, h_length]

            f += [int(size), rl, file[1]]

            try:
                self.files[f[0]] = self.FileStore.append(f)
            except Exception as msg:
                log.add(_("Error while attempting to display folder '%(folder)s', reported error: %(error)s"), {'folder': directory, 'error': msg})

    def OnSave(self, widget):
        sharesdir = os.path.join(self.data_dir, "usershares")

        try:
            if not os.path.exists(sharesdir):
                os.mkdir(sharesdir)
        except Exception as msg:
            log.add(_("Can't create directory '%(folder)s', reported error: %(error)s"), {'folder': sharesdir, 'error': msg})

        try:
            import pickle as mypickle
            import bz2
            sharesfile = bz2.BZ2File(os.path.join(sharesdir, CleanFile(self.user)), 'w')
            mypickle.dump(self.shares, sharesfile, protocol=mypickle.HIGHEST_PROTOCOL)
            sharesfile.close()
        except Exception as msg:
            log.add(_("Can't save shares, '%(user)s', reported error: %(error)s"), {'user': self.user, 'error': msg})

    def saveColumns(self):

        columns = []
        widths = []
        for column in self.FileTreeView.get_columns():
            columns.append(column.get_visible())
            widths.append(column.get_width())
        self.frame.np.config.sections["columns"]["userbrowse"] = columns
        self.frame.np.config.sections["columns"]["userbrowse_widths"] = widths

    def ShowInfo(self, msg):
        self.conn = None
        self.MakeNewModel(msg.list)

    def LoadShares(self, list):
        self.MakeNewModel(list)

    def UpdateGauge(self, msg):

        if msg.total == 0 or msg.bytes == 0:
            fraction = 0.0
        elif msg.bytes >= msg.total:
            fraction = 1.0
        else:
            fraction = float(msg.bytes) / msg.total

        self.progressbar1.set_fraction(fraction)

    def OnSelectDir(self, selection):

        model, iterator = selection.get_selected()

        if iterator is None:
            self.selected_folder = None
            return

        path = model.get_path(iterator)
        directory = model.get_value(iterator, 1)

        self.FolderTreeView.expand_to_path(path)
        self.SetDirectory(directory)

    def OnResort(self, column, column_id):

        model = self.FileTreeView.get_model()

        if model.sort_col == column_id:
            order = model.sort_order

            if order == gtk.SortType.ASCENDING:
                order = gtk.SortType.DESCENDING
            else:
                order = gtk.SortType.ASCENDING

            column.set_sort_order(order)
            model.sort_order = order
            self.FileTreeView.set_model(None)
            model.sort()
            self.FileTreeView.set_model(model)
            return

        cols = self.FileTreeView.get_columns()
        cols[model.sort_col].set_sort_indicator(False)
        cols[column_id].set_sort_indicator(True)
        model.sort_col = column_id

        self.OnResort(column, column_id)

    def OnDownloadDirectory(self, widget):

        if self.selected_folder is not None:
            self.DownloadDirectory(self.selected_folder)

    def OnDownloadDirectoryRecursive(self, widget):

        self.DownloadDirectory(self.selected_folder, "", 1)

    def OnDownloadDirectoryTo(self, widget):

        folder = ChooseDir(self.frame.MainWindow, self.frame.np.config.sections["transfers"]["downloaddir"], multichoice=False)

        if folder is None:
            return

        try:
            self.DownloadDirectory(self.selected_folder, os.path.join(folder[0], ""))
        except IOError:  # failed to open
            log.add('Failed to open %r for reading', folder[0])  # notify user

    def OnDownloadDirectoryRecursiveTo(self, widget):

        folder = ChooseDir(self.frame.MainWindow, self.frame.np.config.sections["transfers"]["downloaddir"], multichoice=False)

        if folder is None:
            return

        try:
            self.DownloadDirectory(self.selected_folder, os.path.join(folder[0], ""), 1)
        except IOError:  # failed to open
            log.add('Failed to open %r for reading', folder[0])  # notify user

    def DownloadDirectory(self, folder, prefix="", recurse=0):

        if folder is None:
            return

        ldir = prefix + folder.split("\\")[-1]

        # Check if folder already exists on system
        ldir = self.frame.np.transfers.FolderDestination(self.user, ldir)

        for d, f in self.shares:

            # Find the wanted directory
            if d != folder:
                continue

            priorityfiles = []
            normalfiles = []

            if self.frame.np.config.sections["transfers"]["prioritize"]:

                for file in f:

                    parts = file[1].rsplit('.', 1)

                    if len(parts) == 2 and parts[1] in ['sfv', 'md5', 'nfo']:
                        priorityfiles.append(file)
                    else:
                        normalfiles.append(file)
            else:
                normalfiles = f

            if self.frame.np.config.sections["transfers"]["reverseorder"]:
                deco = [(x[1], x) for x in normalfiles]
                deco.sort(reverse=True)
                normalfiles = [x for junk, x in deco]

            for file in priorityfiles + normalfiles:

                path = "\\".join([folder, file[1]])
                size = file[2]
                h_bitrate, bitrate, h_length = GetResultBitrateLength(size, file[4])

                self.frame.np.transfers.getFile(
                    self.user,
                    path,
                    ldir,
                    size=size,
                    bitrate=h_bitrate,
                    length=h_length,
                    checkduplicate=True
                )

        if not recurse:
            return

        for subdir, subf in self.shares:
            if dir in subdir and dir != subdir:
                self.DownloadDirectory(subdir, os.path.join(ldir, ""))

    def OnDownloadFiles(self, widget, prefix=""):

        folder = self.selected_folder

        for d, f in self.shares:

            # Find the wanted directory
            if d != folder:
                continue

            for file in f:

                # Find the wanted file
                if file[1] not in self.selected_files:
                    continue

                path = "\\".join([folder, file[1]])
                size = file[2]
                h_bitrate, bitrate, h_length = GetResultBitrateLength(size, file[4])

                # Get the file
                self.frame.np.transfers.getFile(self.user, path, prefix, size=size, bitrate=h_bitrate, length=h_length, checkduplicate=True)

            # We have found the wanted directory: we can break out of the loop
            break

    def OnDownloadFilesTo(self, widget):

        try:
            _, folder = self.selected_folder.rsplit("\\", 1)
        except ValueError:
            folder = self.selected_folder

        path = os.path.join(self.frame.np.config.sections["transfers"]["downloaddir"], folder)

        if os.path.exists(path) and os.path.isdir(path):
            ldir = ChooseDir(self.frame.MainWindow, path, multichoice=False)
        else:
            ldir = ChooseDir(self.frame.MainWindow, self.frame.np.config.sections["transfers"]["downloaddir"], multichoice=False)

        if ldir is None:
            return

        try:
            self.OnDownloadFiles(widget, ldir[0])
        except IOError:  # failed to open
            log.add('failed to open %r for reading', ldir[0])  # notify user

    def OnUploadDirectoryTo(self, widget, recurse=0):

        folder = self.selected_folder

        if folder is None:
            return

        users = []
        for entry in self.frame.np.config.sections["server"]["userlist"]:
            users.append(entry[0])

        users.sort()
        user = ComboBoxDialog(
            parent=self.frame.MainWindow,
            title=_("Upload Directory's Contents"),
            message=_('Enter the User you wish to upload to:'),
            droplist=users
        )

        if user is None or user == "":
            return

        self.frame.np.ProcessRequestToPeer(user, slskmessages.UploadQueueNotification(None))

        self.UploadDirectoryTo(user, folder, recurse)

    def OnUploadDirectoryRecursiveTo(self, widget):
        self.OnUploadDirectoryTo(widget, recurse=1)

    def UploadDirectoryTo(self, user, folder, recurse=0):

        if folder == "" or folder is None or user is None or user == "":
            return

        realpath = self.frame.np.shares.virtual2real(folder)
        ldir = folder.split("\\")[-1]

        for d, f in self.shares:

            # Find the wanted directory
            if d != folder:
                continue

            for file in f:
                filename = "\\".join([folder, file[1]])
                realfilename = "\\".join([realpath, file[1]])
                size = file[2]
                self.frame.np.transfers.pushFile(user, filename, realfilename, ldir, size=size)
                self.frame.np.transfers.checkUploadQueue()

        if not recurse:
            return

        for subdir, subf in self.shares:
            if folder in subdir and folder != subdir:
                self.UploadDirectoryTo(user, subdir, recurse)

    def OnUploadFiles(self, widget, prefix=""):

        folder = self.selected_folder
        realpath = self.frame.np.shares.virtual2real(folder)

        users = []

        for entry in self.frame.np.config.sections["server"]["userlist"]:
            users.append(entry[0])

        users.sort()
        user = ComboBoxDialog(
            parent=self.frame.MainWindow,
            title=_('Upload File(s)'),
            message=_('Enter the User you wish to upload to:'),
            droplist=users
        )

        if user is None or user == "":
            return

        self.frame.np.ProcessRequestToPeer(user, slskmessages.UploadQueueNotification(None))

        for fn in self.selected_files:
            self.frame.np.transfers.pushFile(user, "\\".join([folder, fn]), "\\".join([realpath, fn]), prefix)
            self.frame.np.transfers.checkUploadQueue()

    def OnPlayFiles(self, widget, prefix=""):
        start_new_thread(self._OnPlayFiles, (widget, prefix))

    def _OnPlayFiles(self, widget, prefix=""):

        path = self.frame.np.shares.virtual2real(self.selected_folder)
        executable = self.frame.np.config.sections["players"]["default"]

        if "$" not in executable:
            return

        for fn in self.selected_files:
            file = os.sep.join([path, fn])
            if os.path.exists(file):
                executeCommand(executable, file, background=False)

    def FindMatches(self):

        self.search_list = []

        for directory, files in self.shares:

            if self.query in directory.lower():
                if directory not in self.search_list:
                    self.search_list.append(directory)

            for file in files:
                if self.query in file[1].lower():
                    if directory not in self.search_list:
                        self.search_list.append(directory)

    def OnSearch(self, widget):

        query = self.SearchEntry.get_text().lower()

        if self.query == query:
            self.search_position += 1
        else:
            self.search_position = 0
            self.query = query
            if self.query == "":
                return
            self.FindMatches()

        if self.search_list != []:

            if self.search_position not in list(range(len(self.search_list))):
                self.search_position = 0

            self.search_list.sort()
            directory = self.search_list[self.search_position]

            path = self.DirStore.get_path(self.directories[directory])
            self.FolderTreeView.expand_to_path(path)
            self.FolderTreeView.set_cursor(path)

            # Get matching files in the current directory
            resultfiles = []
            for file in list(self.files.keys()):
                if query in file.lower():
                    resultfiles.append(file)

            sel = self.FileTreeView.get_selection()
            sel.unselect_all()
            l = 1  # noqa: E741
            resultfiles.sort()

            for fn in resultfiles:
                path = self.FileStore.get_path(self.files[fn])

                # Select each matching file in directory
                sel.select_path(path)

                if l:
                    # Position cursor at first match
                    self.FileTreeView.scroll_to_cell(path, None, True, 0.5, 0.5)
                    l = 0  # noqa: E741
        else:
            self.search_position = 0

    def OnClose(self, widget):

        del self.userbrowses.users[self.user]
        self.frame.np.ClosePeerConnection(self.conn)

        self.userbrowses.remove_page(self.Main)
        self.Main.destroy()

    def OnRefresh(self, widget):
        self.FolderTreeView.set_sensitive(False)
        self.FileTreeView.set_sensitive(False)
        self.SaveButton.set_sensitive(False)
        self.frame.BrowseUser(self.user)

    def OnCopyURL(self, widget):

        if self.selected_files != [] and self.selected_files is not None:
            path = "\\".join([self.selected_folder, self.selected_files[0]])
            self.frame.SetClipboardURL(self.user, path)

    def OnCopyDirURL(self, widget):

        if self.selected_folder is None:
            return

        path = self.selected_folder
        if path[:-1] != "/":
            path += "/"

        self.frame.SetClipboardURL(self.user, path)

    def OnFileManager(self, widget):

        if self.selected_folder is None:
            return

        path = self.frame.np.shares.virtual2real(self.selected_folder)
        executable = self.frame.np.config.sections["ui"]["filemanager"]

        if "$" in executable:
            executeCommand(executable, path)
